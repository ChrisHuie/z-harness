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
PAGE_SIZE = 100
MAX_PAGES = 1000
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


def repo_parts(repo, number):
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise RuntimeError("repository must be in owner/name form")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise RuntimeError("gh pr view returned an invalid PR number")
    return parts


def graphql_args(owner, name, number, query, cursor=None):
    args = [
        "gh", "api", "graphql",
    ]
    args.extend([
        "-f", f"owner={owner}",
        "-f", f"name={name}",
        "-F", f"number={number}",
    ])
    if cursor is not None:
        args.extend(["-f", f"endCursor={cursor}"])
    args.extend(["-f", f"query={query}"])
    return args


def pr_identity(pull):
    try:
        identity = {
            "number": pull["number"],
            "url": pull["url"],
            "headRefName": pull["headRefName"],
            "headRefOid": pull["headRefOid"],
            "baseRefOid": pull["baseRefOid"],
            "mergeStateStatus": pull["mergeStateStatus"],
            "isDraft": pull["isDraft"],
            "commitCount": pull["commits"]["totalCount"],
        }
    except (KeyError, TypeError) as exc:
        raise RuntimeError("GitHub GraphQL returned incomplete PR identity state") from exc
    for key in ("url", "headRefName", "headRefOid", "baseRefOid"):
        if not isinstance(identity[key], str) or not identity[key]:
            raise RuntimeError(f"GitHub GraphQL returned an invalid PR {key}")
    if (not isinstance(identity["number"], int)
            or isinstance(identity["number"], bool) or identity["number"] < 1):
        raise RuntimeError("GitHub GraphQL returned an invalid PR number")
    if not isinstance(identity["isDraft"], bool):
        raise RuntimeError("GitHub GraphQL returned an invalid PR isDraft value")
    total = identity["commitCount"]
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise RuntimeError("GitHub GraphQL returned an invalid PR commit totalCount")
    merge_state = identity["mergeStateStatus"]
    if merge_state is not None and not isinstance(merge_state, str):
        raise RuntimeError("GitHub GraphQL returned an invalid PR mergeStateStatus")
    return identity


def parse_graphql_payload(payload):
    if not isinstance(payload, dict) or payload.get("errors"):
        raise RuntimeError("GitHub GraphQL returned errors or a non-object response")
    try:
        pull = payload["data"]["repository"]["pullRequest"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("GitHub GraphQL returned incomplete PR state") from exc
    if not isinstance(pull, dict):
        raise RuntimeError("GitHub GraphQL returned no pull request")
    return pull


def same_identity(left, right):
    keys = (
        "number", "url", "headRefName", "headRefOid", "baseRefOid",
        "mergeStateStatus", "isDraft", "commitCount",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def github_checks(cwd, repo, number):
    owner, name = repo_parts(repo, number)
    query = (
        "query($owner:String!,$name:String!,$number:Int!,$endCursor:String){"
        "repository(owner:$owner,name:$name){pullRequest(number:$number){"
        "number url headRefName headRefOid baseRefOid mergeStateStatus isDraft "
        "commits{totalCount} statusCheckRollup{contexts(first:100,after:$endCursor){"
        "totalCount pageInfo{hasNextPage endCursor} nodes{__typename "
        "... on CheckRun{id name status conclusion detailsUrl} "
        "... on StatusContext{id context state targetUrl}}}}}}}"
    )
    identity = None
    total = None
    signals = []
    signal_ids = set()
    cursors = set()
    cursor = None
    page = 1
    while True:
        payload = json_command(
            graphql_args(owner, name, number, query, cursor=cursor), cwd)
        pull = parse_graphql_payload(payload)
        page_identity = pr_identity(pull)
        if identity is None:
            identity = page_identity
        elif not same_identity(identity, page_identity):
            raise RuntimeError("PR state moved while paginating exact-head checks")

        rollup = pull.get("statusCheckRollup")
        if rollup is None:
            page_total, nodes = 0, []
            page_info = {"hasNextPage": False, "endCursor": None}
        else:
            try:
                connection = rollup["contexts"]
                page_total = connection["totalCount"]
                nodes = connection["nodes"]
                page_info = connection["pageInfo"]
            except (KeyError, TypeError) as exc:
                raise RuntimeError("GitHub GraphQL returned incomplete check pagination") from exc
        if (not isinstance(page_total, int) or isinstance(page_total, bool)
                or page_total < 0 or not isinstance(nodes, list)):
            raise RuntimeError("GitHub GraphQL returned invalid check pagination counts")
        if total is None:
            total = page_total
        elif total != page_total:
            raise RuntimeError("exact-head check total changed during pagination")
        if not isinstance(page_info, dict) or not isinstance(
                page_info.get("hasNextPage"), bool):
            raise RuntimeError("GitHub GraphQL returned invalid check pageInfo")
        has_next = page_info["hasNextPage"]
        for node in nodes:
            if not isinstance(node, dict):
                raise RuntimeError("GitHub GraphQL returned a malformed check node")
            signal_id = node.get("id")
            if not isinstance(signal_id, str) or not signal_id:
                raise RuntimeError("GitHub GraphQL returned a check without an id")
            if signal_id in signal_ids:
                raise RuntimeError("GitHub GraphQL returned a duplicate check id")
            signal_ids.add(signal_id)
            signals.append(node)
        if not has_next:
            break
        next_cursor = page_info.get("endCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            raise RuntimeError("GitHub GraphQL returned no cursor for the next check page")
        if next_cursor in cursors:
            raise RuntimeError("GitHub GraphQL repeated a check-page cursor")
        cursors.add(next_cursor)
        cursor = next_cursor
        page += 1
        if page > MAX_PAGES:
            raise RuntimeError("GitHub GraphQL pagination exceeded its safety bound")

    if len(signals) != total:
        raise RuntimeError(
            f"GitHub returned {len(signals)} of {total} exact-head checks")
    identity["statusCheckRollup"] = signals
    return identity


def parse_run_page(payload):
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub Actions returned a non-object response")
    total = payload.get("total_count")
    runs = payload.get("workflow_runs")
    if (not isinstance(total, int) or isinstance(total, bool) or total < 0
            or not isinstance(runs, list)):
        raise RuntimeError("GitHub Actions returned invalid pagination state")
    return total, runs


def run_page_args(repo, head, page):
    return [
        "gh", "api", "-X", "GET", f"repos/{repo}/actions/runs",
        "-f", f"head_sha={head}", "-F", f"per_page={PAGE_SIZE}",
        "-F", f"page={page}",
    ]


def github_workflow_runs(cwd, repo, head):
    page = 1
    expected_total = None
    raw_runs = []
    run_ids = set()
    first_page_ids = None
    while True:
        payload = json_command(run_page_args(repo, head, page), cwd)
        total, page_runs = parse_run_page(payload)
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise RuntimeError("exact-head workflow-run total changed during pagination")
        page_ids = []
        for run in page_runs:
            if not isinstance(run, dict):
                raise RuntimeError("GitHub Actions returned a malformed workflow run")
            run_id = run.get("id")
            if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
                raise RuntimeError("GitHub Actions returned a workflow run without a valid id")
            if run_id in run_ids:
                raise RuntimeError("GitHub Actions returned a duplicate workflow-run id")
            run_ids.add(run_id)
            page_ids.append(run_id)
            raw_runs.append(run)
        if page == 1:
            first_page_ids = page_ids
        if len(raw_runs) >= expected_total:
            break
        if not page_runs:
            raise RuntimeError("GitHub Actions pagination stopped before its last page")
        page += 1
        if page > MAX_PAGES:
            raise RuntimeError("GitHub Actions pagination exceeded its safety bound")
    if len(raw_runs) != expected_total:
        raise RuntimeError(
            f"GitHub returned {len(raw_runs)} of {expected_total} exact-head workflow runs")

    replay_total, replay_runs = parse_run_page(
        json_command(run_page_args(repo, head, 1), cwd))
    replay_ids = [run.get("id") for run in replay_runs if isinstance(run, dict)]
    if replay_total != expected_total or replay_ids != first_page_ids:
        raise RuntimeError("exact-head workflow runs changed during pagination")

    normalized = []
    for run in raw_runs:
        normalized.append({
            "databaseId": run["id"],
            "workflowName": run.get("name"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "headSha": run.get("head_sha"),
            "url": run.get("html_url"),
        })
    return normalized


def github_snapshot(cwd, repo, number):
    owner, name = repo_parts(repo, number)
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){pullRequest(number:$number){"
        "number url headRefName headRefOid baseRefOid mergeStateStatus isDraft "
        "commits{totalCount}}}}"
    )
    return pr_identity(parse_graphql_payload(json_command(
        graphql_args(owner, name, number, query), cwd)))


def github_state(cwd, pr, repo):
    fields = "number,url,headRefName,headRefOid,baseRefOid"
    view = json_command(
        ["gh", "pr", "view", pr, "--repo", repo, "--json", fields], cwd
    )
    if not isinstance(view, dict):
        raise RuntimeError("gh pr view output is not an object")
    number = view.get("number")
    repo_parts(repo, number)
    for key in ("url", "headRefName", "headRefOid", "baseRefOid"):
        if not isinstance(view.get(key), str) or not view[key]:
            raise RuntimeError(f"gh pr view returned an invalid {key}")

    graph = github_checks(cwd, repo, number)
    for key in ("number", "url", "headRefName", "headRefOid", "baseRefOid"):
        if view.get(key) != graph.get(key):
            raise RuntimeError(f"PR {key} moved while collecting GitHub delivery state")
    runs = github_workflow_runs(cwd, repo, graph["headRefOid"])
    final = github_snapshot(cwd, repo, number)
    if not same_identity(graph, final):
        raise RuntimeError("PR state moved while collecting GitHub delivery state")
    return graph, runs


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
    merge_state = pr.get("mergeStateStatus")
    known_merge_states = {
        "BEHIND", "BLOCKED", "CLEAN", "DIRTY", "DRAFT", "HAS_HOOKS",
        "UNKNOWN", "UNSTABLE",
    }
    if (not isinstance(merge_state, str) or not merge_state.strip()
            or merge_state.upper() not in known_merge_states
            or merge_state.upper() == "UNKNOWN"):
        evidence_errors.append("GitHub returned no usable PR merge state")
    elif merge_state.upper() != "CLEAN":
        reasons.append(f"GitHub merge state is {merge_state.upper()}, not CLEAN")
    if pr.get("isDraft") is True:
        reasons.append("GitHub reports that the pull request is a draft")
    elif pr.get("isDraft") is not False:
        evidence_errors.append("GitHub returned no usable PR draft state")
    if checks["failed"] or run_counts["failed"]:
        reasons.append("one or more exact-head checks failed")

    commit_count = pr.get("commitCount")
    if (not isinstance(commit_count, int) or isinstance(commit_count, bool)
            or commit_count < 1):
        evidence_errors.append("GitHub returned zero PR commits")
    base = pr.get("baseRefOid")
    if not isinstance(base, str) or not base:
        evidence_errors.append("GitHub returned no PR base OID")
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
        "pr_base": base,
        "pr_commit_count": commit_count,
        "merge_state": merge_state,
        "is_draft": pr.get("isDraft"),
        "checks": checks,
        "exact_head_runs": run_counts,
        "verdict": verdict,
        "reasons": reasons,
    }, code


def print_report(report):
    print("PR DELIVERY STATE")
    for key in (
        "workspace_changes", "local_branch", "local_head", "pr_number", "pr_url",
        "remote_pr_branch", "pr_head", "pr_base", "pr_commit_count", "merge_state",
        "is_draft",
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
    base = "b" * 40
    local = {"branch": "feature/review", "head": head, "workspace_changes": 0}
    pr = {
        "number": 7, "url": "https://github.com/o/r/pull/7", "headRefName": "feature/review",
        "headRefOid": head, "baseRefOid": base, "commitCount": 147,
        "mergeStateStatus": "CLEAN", "isDraft": False,
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

    original_json_command = globals()["json_command"]

    def graph_payload(nodes, total=None, has_next=False, cursor=None,
                      head="a" * 40, base="b" * 40, merge="CLEAN",
                      draft=False, commits=147):
        if total is None:
            total = len(nodes)
        return {"data": {"repository": {"pullRequest": {
            "number": 7,
            "url": "https://github.com/o/r/pull/7",
            "headRefName": "feature/review",
            "headRefOid": head,
            "baseRefOid": base,
            "mergeStateStatus": merge,
            "isDraft": draft,
            "commits": {"totalCount": commits},
            "statusCheckRollup": {"contexts": {
                "totalCount": total,
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                "nodes": nodes,
            }},
        }}}}

    def check_node(index, conclusion="SUCCESS"):
        return {
            "__typename": "CheckRun", "id": f"C{index}",
            "name": f"check-{index}", "status": "COMPLETED",
            "conclusion": conclusion, "detailsUrl": f"https://ci/{index}",
        }

    def raw_run(index, conclusion="success", head="a" * 40):
        return {
            "id": index, "name": f"workflow-{index}", "status": "completed",
            "conclusion": conclusion, "head_sha": head,
            "html_url": f"https://ci/run/{index}",
        }

    local, pr, runs = fixture()
    report, code = evaluate(local, pr, runs)
    check("matching local, PR, and exact-head CI passes", code == 0 and
          report["verdict"] == "PUBLISHED_AND_GREEN"
          and report["pr_commit_count"] == 147 and report["pr_base"] == "b" * 40)

    local, pr, runs = fixture()
    local["head"] = "c" * 40
    report, code = evaluate(local, pr, runs)
    check("local-only commit state fails", code == 1 and
          "local HEAD differs" in " ".join(report["reasons"]))

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

    merge_evidence_results = []
    for state in (None, "", "UNKNOWN", "FUTURE"):
        local, pr, runs = fixture()
        pr["mergeStateStatus"] = state
        _report, code = evaluate(local, pr, runs)
        merge_evidence_results.append(code == 2)
    check("missing, empty, UNKNOWN, and unrecognized merge states are evidence errors",
          all(merge_evidence_results))

    nonclean_results = []
    for state in ("DIRTY", "BLOCKED", "UNSTABLE", "BEHIND"):
        local, pr, runs = fixture()
        pr["mergeStateStatus"] = state
        _report, code = evaluate(local, pr, runs)
        nonclean_results.append(code == 1)
    check("known non-CLEAN merge states cannot pass", all(nonclean_results))

    local, pr, runs = fixture()
    pr["isDraft"] = True
    _report, code = evaluate(local, pr, runs)
    check("draft pull requests cannot pass", code == 1)

    local, pr, runs = fixture()
    pr["baseRefOid"] = ""
    _report, code = evaluate(local, pr, runs)
    check("a missing base OID is an evidence error", code == 2)

    invalid_query_inputs_rejected = []
    for repo, number in (("owner", 7), ("/repo", 7), ("owner/repo/extra", 7),
                         ("owner/repo", 0), ("owner/repo", True)):
        try:
            repo_parts(repo, number)
            invalid_query_inputs_rejected.append(False)
        except RuntimeError:
            invalid_query_inputs_rejected.append(True)
    check("malformed repositories and PR numbers fail before a GitHub query",
          all(invalid_query_inputs_rejected))

    invalid_graphql_rejected = []
    for payload in ({}, {"errors": [{"message": "denied"}]},
                    {"data": {"repository": {"pullRequest": None}}}):
        try:
            parse_graphql_payload(payload)
            invalid_graphql_rejected.append(False)
        except RuntimeError:
            invalid_graphql_rejected.append(True)
    check("malformed, errored, and absent GraphQL PR payloads are rejected",
          all(invalid_graphql_rejected))

    check_calls = []

    def paginated_checks(args, _cwd):
        check_calls.append(args)
        if "endCursor=cursor-1" in args:
            return graph_payload([check_node(100, "FAILURE")], 101)
        return graph_payload(
            [check_node(i) for i in range(100)], 101, True, "cursor-1")

    try:
        globals()["json_command"] = paginated_checks
        collected = github_checks(".", "o/r", 7)
    finally:
        globals()["json_command"] = original_json_command
    check("the 101st exact-head check is collected and can fail the verdict",
          len(collected["statusCheckRollup"]) == 101
          and summarize_signals(collected["statusCheckRollup"])["failed"] == 1
          and len(check_calls) == 2 and "endCursor=cursor-1" in check_calls[1])

    def truncated_checks(_args, _cwd):
        return graph_payload([check_node(i) for i in range(100)], 101)

    try:
        globals()["json_command"] = truncated_checks
        try:
            github_checks(".", "o/r", 7)
            truncated_checks_rejected = False
        except RuntimeError:
            truncated_checks_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("an incomplete exact-head check total is rejected", truncated_checks_rejected)

    def moving_check_base(args, _cwd):
        if "endCursor=cursor-1" in args:
            return graph_payload([check_node(2)], 2, base="c" * 40)
        return graph_payload([check_node(1)], 2, True, "cursor-1")

    try:
        globals()["json_command"] = moving_check_base
        try:
            github_checks(".", "o/r", 7)
            moving_check_base_rejected = False
        except RuntimeError:
            moving_check_base_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("a base change between check pages is rejected", moving_check_base_rejected)

    run_calls = []
    raw_runs = [raw_run(i) for i in range(1, 101)] + [raw_run(101, "failure")]

    def paginated_runs(args, _cwd):
        run_calls.append(args)
        page = int(next(value.split("=", 1)[1] for value in args if value.startswith("page=")))
        page_runs = raw_runs[:100] if page == 1 else raw_runs[100:] if page == 2 else []
        return {"total_count": 101, "workflow_runs": page_runs}

    try:
        globals()["json_command"] = paginated_runs
        collected_runs = github_workflow_runs(".", "o/r", "a" * 40)
    finally:
        globals()["json_command"] = original_json_command
    run_pages = [int(next(value.split("=", 1)[1] for value in args
                          if value.startswith("page="))) for args in run_calls]
    check("workflow-run pagination collects and evaluates the 101st run",
          len(collected_runs) == 101 and summarize_signals(collected_runs)["failed"] == 1
          and run_pages == [1, 2, 1])

    twenty_one = [raw_run(i) for i in range(1, 21)] + [raw_run(21, "failure")]

    def twenty_one_runs(_args, _cwd):
        return {"total_count": 21, "workflow_runs": twenty_one}

    try:
        globals()["json_command"] = twenty_one_runs
        collected_runs = github_workflow_runs(".", "o/r", "a" * 40)
    finally:
        globals()["json_command"] = original_json_command
    check("a failing 21st workflow run cannot disappear behind a default cap",
          len(collected_runs) == 21 and summarize_signals(collected_runs)["failed"] == 1)

    def incomplete_runs(args, _cwd):
        page = int(next(value.split("=", 1)[1] for value in args if value.startswith("page=")))
        return {"total_count": 101,
                "workflow_runs": [raw_run(i) for i in range(1, 101)] if page == 1 else []}

    try:
        globals()["json_command"] = incomplete_runs
        try:
            github_workflow_runs(".", "o/r", "a" * 40)
            incomplete_runs_rejected = False
        except RuntimeError:
            incomplete_runs_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("an incomplete workflow-run total is rejected", incomplete_runs_rejected)

    replay_calls = 0

    def changing_runs(_args, _cwd):
        nonlocal replay_calls
        replay_calls += 1
        item = raw_run(1 if replay_calls == 1 else 2)
        return {"total_count": 1, "workflow_runs": [item]}

    try:
        globals()["json_command"] = changing_runs
        try:
            github_workflow_runs(".", "o/r", "a" * 40)
            changing_runs_rejected = False
        except RuntimeError:
            changing_runs_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("workflow-run churn during collection is rejected", changing_runs_rejected)

    state_calls = []

    def complete_state(args, _cwd):
        state_calls.append(args)
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 7, "url": "https://github.com/o/r/pull/7",
                "headRefName": "feature/review", "headRefOid": "a" * 40,
                "baseRefOid": "b" * 40,
            }
        if args[:3] == ["gh", "api", "graphql"]:
            payload = graph_payload([check_node(1)])
            return payload
        if args[:5] == ["gh", "api", "-X", "GET", "repos/o/r/actions/runs"]:
            return {"total_count": 1, "workflow_runs": [raw_run(1)]}
        raise AssertionError(args)

    try:
        globals()["json_command"] = complete_state
        queried_pr, queried_runs = github_state(".", "7", "o/r")
    finally:
        globals()["json_command"] = original_json_command
    view_call = state_calls[0]
    check_call = next(args for args in state_calls
                      if any("$endCursor" in value for value in args))
    rest_calls = [args for args in state_calls if args[:5]
                  == ["gh", "api", "-X", "GET", "repos/o/r/actions/runs"]]
    check("GitHub state binds base and head around complete check and run pagination",
          queried_pr["commitCount"] == 147 and len(queried_runs) == 1
          and view_call[-1] == "number,url,headRefName,headRefOid,baseRefOid"
          and any("contexts(first:100,after:$endCursor)" in value
                  for value in check_call)
          and len(rest_calls) == 2
          and all("per_page=100" in args and "head_sha=" + "a" * 40 in args
                  for args in rest_calls)
          and all(value.count("{") == value.count("}")
                  for args in state_calls for value in args if value.startswith("query="))
          and not any(args[:3] == ["gh", "run", "list"] for args in state_calls))

    final_snapshot_calls = 0

    def moved_base_after_collection(args, _cwd):
        nonlocal final_snapshot_calls
        if args[:3] == ["gh", "pr", "view"]:
            return {
                "number": 7, "url": "https://github.com/o/r/pull/7",
                "headRefName": "feature/review", "headRefOid": "a" * 40,
                "baseRefOid": "b" * 40,
            }
        if args[:3] == ["gh", "api", "graphql"]:
            if any("$endCursor" in value for value in args):
                return graph_payload([check_node(1)])
            final_snapshot_calls += 1
            return graph_payload([check_node(1)], base="c" * 40)
        if args[:5] == ["gh", "api", "-X", "GET", "repos/o/r/actions/runs"]:
            return {"total_count": 1, "workflow_runs": [raw_run(1)]}
        raise AssertionError(args)

    try:
        globals()["json_command"] = moved_base_after_collection
        try:
            github_state(".", "7", "o/r")
            moved_base_rejected = False
        except RuntimeError:
            moved_base_rejected = True
    finally:
        globals()["json_command"] = original_json_command
    check("a base change after green checks and runs is rejected",
          moved_base_rejected and final_snapshot_calls == 1)

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
