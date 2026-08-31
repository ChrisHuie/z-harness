#!/usr/bin/env python3
"""pr-delivery-state — prove whether local PR work is published and green.

The command keeps four states separate: workspace changes, local commits, the
GitHub PR head, and exact-head CI. It never treats `git commit` as publication.

  pr-delivery-state.py --pr <number-or-url> [--repo <owner/repo>] [--json]
  pr-delivery-state.py --selftest

Exit codes: 0 published and green · 1 unpublished/conflicting/failed ·
2 usage, dependency, or zero-evidence error · 3 exact-head CI still pending.
"""
import json
import os
import subprocess
import sys

VERSION = "1.0.0"
PASS_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
FAIL_CONCLUSIONS = {
    "ACTION_REQUIRED", "CANCELLED", "FAILURE", "STALE", "STARTUP_FAILURE", "TIMED_OUT"
}


def command(args, cwd):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required command not found: {args[0]}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(args[:3])}: {detail}")
    return result.stdout.strip()


def json_command(args, cwd):
    raw = command(args, cwd)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(args[:3])}: output is not JSON") from exc


def local_state(cwd):
    top = command(["git", "rev-parse", "--show-toplevel"], cwd)
    return {
        "root": top,
        "branch": command(["git", "branch", "--show-current"], top),
        "head": command(["git", "rev-parse", "HEAD"], top),
        "workspace_changes": len(command(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], top
        ).splitlines()),
    }


def repo_name(cwd, requested):
    if requested:
        return requested
    data = json_command(["gh", "repo", "view", "--json", "nameWithOwner"], cwd)
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not name:
        raise RuntimeError("gh repo view returned no nameWithOwner")
    return name


def parse_commit_total(payload, expected_head):
    if not isinstance(payload, dict) or payload.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors or a non-object response")
    try:
        pull = payload["data"]["repository"]["pullRequest"]
        graph_head = pull["headRefOid"]
        total = pull["commits"]["totalCount"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("GitHub GraphQL returned incomplete PR commit state") from exc
    if not isinstance(graph_head, str) or not graph_head:
        raise RuntimeError("GitHub GraphQL returned an invalid PR headRefOid")
    if graph_head != expected_head:
        raise RuntimeError("PR head moved while collecting GitHub delivery state")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise RuntimeError("GitHub GraphQL returned an invalid PR commit totalCount")
    return total


def github_commit_count(cwd, repo, number, expected_head):
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise RuntimeError("repository must be in owner/name form")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise RuntimeError("gh pr view returned an invalid PR number")
    owner, name = parts
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){pullRequest(number:$number){"
        "headRefOid commits{totalCount}}}}"
    )
    payload = json_command([
        "gh", "api", "graphql",
        "-f", f"owner={owner}",
        "-f", f"name={name}",
        "-F", f"number={number}",
        "-f", f"query={query}",
    ], cwd)
    return parse_commit_total(payload, expected_head)


def github_state(cwd, pr, repo):
    fields = "number,url,headRefName,headRefOid,mergeStateStatus,statusCheckRollup"
    view = json_command(
        ["gh", "pr", "view", pr, "--repo", repo, "--json", fields], cwd
    )
    if not isinstance(view, dict):
        raise RuntimeError("gh pr view output is not an object")
    head = view.get("headRefOid")
    if not head:
        raise RuntimeError("gh pr view returned no headRefOid")
    runs = json_command([
        "gh", "run", "list", "--repo", repo, "--commit", head,
        "--json", "databaseId,workflowName,status,conclusion,headSha,url",
    ], cwd)
    if not isinstance(runs, list):
        raise RuntimeError("gh run list output is not an array")
    view["commitCount"] = github_commit_count(
        cwd, repo, view.get("number"), head)
    return view, runs


def signal_bucket(signal):
    state = str(signal.get("state") or "").upper()
    status = str(signal.get("status") or "").upper()
    conclusion = str(signal.get("conclusion") or "").upper()
    if state:
        if state == "SUCCESS":
            return "passed"
        if state in {"PENDING", "EXPECTED"}:
            return "pending"
        return "failed"
    if status and status != "COMPLETED":
        return "pending"
    if conclusion in PASS_CONCLUSIONS:
        return "passed"
    if conclusion in FAIL_CONCLUSIONS or conclusion:
        return "failed"
    return "pending"


def summarize_signals(signals):
    counts = {"total": len(signals), "passed": 0, "pending": 0, "failed": 0}
    for signal in signals:
        counts[signal_bucket(signal)] += 1
    return counts


def evaluate(local, pr, runs):
    checks = summarize_signals(pr.get("statusCheckRollup") or [])
    run_counts = summarize_signals(runs)
    reasons = []
    evidence_errors = []
    if local["workspace_changes"]:
        reasons.append(f"workspace has {local['workspace_changes']} change(s)")
    if local["branch"] != pr.get("headRefName"):
        reasons.append(
            f"local branch {local['branch']!r} differs from PR branch {pr.get('headRefName')!r}"
        )
    if local["head"] != pr.get("headRefOid"):
        reasons.append("local HEAD differs from the GitHub PR head")
    if pr.get("mergeStateStatus") == "DIRTY":
        reasons.append("GitHub reports a conflicting merge state")
    if checks["failed"] or run_counts["failed"]:
        reasons.append("one or more exact-head checks failed")

    commit_count = pr.get("commitCount")
    if (not isinstance(commit_count, int) or isinstance(commit_count, bool)
            or commit_count < 1):
        evidence_errors.append("GitHub returned zero PR commits")
    if checks["total"] == 0 or run_counts["total"] == 0:
        evidence_errors.append("exact-head check and workflow-run lists must both be non-empty")
    wrong_head_runs = [run for run in runs if run.get("headSha") != pr.get("headRefOid")]
    if wrong_head_runs:
        evidence_errors.append(f"{len(wrong_head_runs)} workflow run(s) do not match the PR head")

    if evidence_errors:
        verdict, code = "ZERO_EXACT_HEAD_CI_EVIDENCE", 2
        reasons.extend(evidence_errors)
    elif reasons:
        verdict, code = "NOT_PUBLISHED_OR_GREEN", 1
    elif checks["pending"] or run_counts["pending"]:
        verdict, code = "EXACT_HEAD_CI_PENDING", 3
        reasons.append("one or more exact-head checks are pending")
    else:
        verdict, code = "PUBLISHED_AND_GREEN", 0

    return {
        "workspace_changes": local["workspace_changes"],
        "local_branch": local["branch"],
        "local_head": local["head"],
        "pr_number": pr.get("number"),
        "pr_url": pr.get("url"),
        "remote_pr_branch": pr.get("headRefName"),
        "pr_head": pr.get("headRefOid"),
        "pr_commit_count": commit_count,
        "merge_state": pr.get("mergeStateStatus"),
        "checks": checks,
        "exact_head_runs": run_counts,
        "verdict": verdict,
        "reasons": reasons,
    }, code


def print_report(report):
    print("PR DELIVERY STATE")
    for key in (
        "workspace_changes", "local_branch", "local_head", "pr_number", "pr_url",
        "remote_pr_branch", "pr_head", "pr_commit_count", "merge_state",
    ):
        print(f"  {key}: {report[key]}")
    for key in ("checks", "exact_head_runs"):
        value = report[key]
        print(
            f"  {key}: {value['total']} total / {value['passed']} passed / "
            f"{value['pending']} pending / {value['failed']} failed"
        )
    print(f"  verdict: {report['verdict']}")
    for reason in report["reasons"]:
        print(f"  reason: {reason}")


def fixture():
    head = "a" * 40
    local = {"branch": "feature/review", "head": head, "workspace_changes": 0}
    pr = {
        "number": 7, "url": "https://github.com/o/r/pull/7", "headRefName": "feature/review",
        "headRefOid": head, "commitCount": 147, "mergeStateStatus": "CLEAN",
        "statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    }
    runs = [{"status": "completed", "conclusion": "success", "headSha": head}]
    return local, pr, runs


def selftest():
    failures = checks = 0

    def check(name, condition):
        nonlocal failures, checks
        checks += 1
        print(f"  {'PASS' if condition else 'FAIL'} {name}")
        failures += not condition

    local, pr, runs = fixture()
    report, code = evaluate(local, pr, runs)
    check("matching local, PR, and exact-head CI passes", code == 0 and
          report["verdict"] == "PUBLISHED_AND_GREEN"
          and report["pr_commit_count"] == 147)

    local, pr, runs = fixture()
    local["head"] = "b" * 40
    report, code = evaluate(local, pr, runs)
    check("local-only commit state fails", code == 1 and "local HEAD differs" in " ".join(
        report["reasons"]))

    local, pr, runs = fixture()
    local["workspace_changes"] = 2
    _report, code = evaluate(local, pr, runs)
    check("uncommitted workspace changes fail", code == 1)

    local, pr, _runs = fixture()
    report, code = evaluate(local, pr, [])
    check("zero exact-head runs is an evidence error", code == 2 and
          report["verdict"] == "ZERO_EXACT_HEAD_CI_EVIDENCE")

    local, pr, runs = fixture()
    runs[0]["status"] = "in_progress"
    runs[0]["conclusion"] = ""
    report, code = evaluate(local, pr, runs)
    check("pending exact-head run is distinct", code == 3 and
          report["verdict"] == "EXACT_HEAD_CI_PENDING")

    local, pr, runs = fixture()
    pr["statusCheckRollup"][0]["conclusion"] = "FAILURE"
    _report, code = evaluate(local, pr, runs)
    check("failed exact-head check fails", code == 1)

    local, pr, runs = fixture()
    pr["commitCount"] = 0
    _report, code = evaluate(local, pr, runs)
    check("zero PR commits is an evidence error", code == 2)

    local, pr, runs = fixture()
    runs[0]["headSha"] = "c" * 40
    _report, code = evaluate(local, pr, runs)
    check("wrong-head workflow run is an evidence error", code == 2)

    invalid_totals_rejected = []
    for payload in (
            {},
            {"data": {"repository": {"pullRequest": {"commits": {"totalCount": True}}}}},
            {"data": {"repository": {"pullRequest": {"commits": {"totalCount": -1}}}}},
    ):
        try:
            parse_commit_total(payload, "a" * 40)
            invalid_totals_rejected.append(False)
        except RuntimeError:
            invalid_totals_rejected.append(True)
    check("missing, boolean, and negative GraphQL commit totals are rejected",
          all(invalid_totals_rejected))

    invalid_states_rejected = []
    for payload in (
            {"errors": [{"message": "denied"}], "data": {"repository": {
                "pullRequest": {
                    "headRefOid": "a" * 40, "commits": {"totalCount": 147},
                },
            }}},
            {"data": {"repository": {"pullRequest": {
                "headRefOid": "b" * 40, "commits": {"totalCount": 147},
            }}}},
            {"data": {"repository": {"pullRequest": {
                "commits": {"totalCount": 147},
            }}}},
    ):
        try:
            parse_commit_total(payload, "a" * 40)
            invalid_states_rejected.append(False)
        except RuntimeError:
            invalid_states_rejected.append(True)
    check("GraphQL errors, head movement, and missing heads are rejected",
          all(invalid_states_rejected))

    invalid_query_inputs_rejected = []
    invalid_query_called = False

    def reject_invalid_query(_args, _cwd):
        nonlocal invalid_query_called
        invalid_query_called = True
        raise AssertionError("invalid query input reached gh")

    original_json_command = globals()["json_command"]
    try:
        globals()["json_command"] = reject_invalid_query
        for repo, number in (("owner", 7), ("/repo", 7), ("owner/repo/extra", 7),
                             ("owner/repo", 0), ("owner/repo", True)):
            try:
                github_commit_count(".", repo, number, "a" * 40)
                invalid_query_inputs_rejected.append(False)
            except RuntimeError:
                invalid_query_inputs_rejected.append(True)
    finally:
        globals()["json_command"] = original_json_command
    check("malformed repositories and PR numbers fail before a GraphQL query",
          all(invalid_query_inputs_rejected) and not invalid_query_called)

    calls = []

    def fake_json_command(args, cwd):
        calls.append(args)
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 7, "url": "https://github.com/o/r/pull/7",
                "headRefName": "feature/review", "headRefOid": "a" * 40,
                "mergeStateStatus": "CLEAN", "statusCheckRollup": [],
            }
        if args[:3] == ["gh", "api", "graphql"]:
            return {"data": {"repository": {"pullRequest": {
                "headRefOid": "a" * 40, "commits": {"totalCount": 147},
            }}}}
        if args[:3] == ["gh", "run", "list"]:
            return []
        raise AssertionError(args)

    try:
        globals()["json_command"] = fake_json_command
        queried_pr, queried_runs = github_state(".", "7", "o/r")
    finally:
        globals()["json_command"] = original_json_command
    view_call = next(args for args in calls if args[:3] == ["gh", "pr", "view"])
    graphql_call = next(args for args in calls if args[:3] == ["gh", "api", "graphql"])
    expected_query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){pullRequest(number:$number){"
        "headRefOid commits{totalCount}}}}"
    )
    check("GitHub state uses GraphQL totalCount rather than the capped commit-node list",
          queried_pr["commitCount"] == 147 and queried_runs == []
          and calls[0][:3] == ["gh", "pr", "view"]
          and calls[1][:3] == ["gh", "run", "list"]
          and calls[2] == [
              "gh", "api", "graphql", "-f", "owner=o", "-f", "name=r",
              "-F", "number=7", "-f", f"query={expected_query}",
          ]
          and view_call[-1]
          == "number,url,headRefName,headRefOid,mergeStateStatus,statusCheckRollup"
          and "headRefOid commits{totalCount}" in graphql_call[-1])

    def graphql_error_after_view(args, _cwd):
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 7, "url": "https://github.com/o/r/pull/7",
                "headRefName": "feature/review", "headRefOid": "a" * 40,
                "mergeStateStatus": "CLEAN", "statusCheckRollup": [],
            }
        if args[:3] == ["gh", "run", "list"]:
            return []
        if args[:3] == ["gh", "api", "graphql"]:
            return {"errors": [{"message": "denied"}], "data": {"repository": {
                "pullRequest": {
                    "headRefOid": "a" * 40, "commits": {"totalCount": 100},
                },
            }}}
        raise AssertionError(args)

    try:
        globals()["json_command"] = graphql_error_after_view
        try:
            github_state(".", "7", "o/r")
            graphql_error_rejected = False
        except RuntimeError:
            graphql_error_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("GraphQL errors never fall back to a capped commit count",
          graphql_error_rejected)

    def malformed_view(_args, _cwd):
        return []

    try:
        globals()["json_command"] = malformed_view
        try:
            github_state(".", "7", "o/r")
            malformed_view_rejected = False
        except RuntimeError:
            malformed_view_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("a malformed PR-view response is an instrument error",
          malformed_view_rejected)

    print(f"\n  {checks} checks, {failures} failure(s)")
    print(f"SELFTEST-SUMMARY suite=pr-delivery-state checks={checks} failures={failures}")
    return 1 if failures else 0


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if args == ["--version"]:
        print(f"pr-delivery-state {VERSION}")
        return 0
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if args else 2

    pr = repo = None
    json_output = False
    index = 0
    while index < len(args):
        if args[index] == "--pr" and index + 1 < len(args):
            pr, index = args[index + 1], index + 2
        elif args[index] == "--repo" and index + 1 < len(args):
            repo, index = args[index + 1], index + 2
        elif args[index] == "--json":
            json_output, index = True, index + 1
        else:
            sys.stderr.write(f"unknown or incomplete argument: {args[index]!r}\n")
            return 2
    if not pr:
        sys.stderr.write("--pr <number-or-url> is required\n")
        return 2

    try:
        local = local_state(os.getcwd())
        repo = repo_name(local["root"], repo)
        pr_state, runs = github_state(local["root"], pr, repo)
        report, code = evaluate(local, pr_state, runs)
    except RuntimeError as exc:
        sys.stderr.write(f"pr-delivery-state: {exc}\n")
        return 2
    if json_output:
        print(json.dumps(report, sort_keys=True))
    else:
        print_report(report)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
