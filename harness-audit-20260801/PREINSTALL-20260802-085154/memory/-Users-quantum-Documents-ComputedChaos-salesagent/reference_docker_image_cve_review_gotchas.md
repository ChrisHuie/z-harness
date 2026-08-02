---
name: reference_docker_image_cve_review_gotchas
description: How to empirically review a container-image CVE fix (Dockerfile PR) + Trivy/go/buildx gotchas that produce wrong conclusions
metadata: 
  node_type: memory
  type: reference
  originSessionId: 9c03f987-7ecb-4a12-92bd-eafed37f6084
---

Reviewing a Dockerfile / container-image CVE PR (e.g. patching base-image + a Go tool). The real review is EMPIRICAL — build the image with the CI gate's exact flags and scan — not the Python/AdCP `review-*` agents (a Dockerfile-only diff gives them no surface). Run the Dockerfile structural guard: `test_architecture_dockerfile_digest_pinned.py` (digest-pin + non-root). Prove the fix is causal: build BOTH `origin/main`'s Dockerfile (before) and HEAD (after), scan both, confirm the cited CVEs are present-then-gone and the gate exit flips 1→0. See [[feedback_empirical_over_static_guard_assessment]].

Tool gotchas that gave me WRONG intermediate conclusions this session:

- **Trivy `fs` vs `rootfs` for Go binaries.** `trivy fs <file-or-dir>` does NOT run the gobinary analyzer on a standalone binary — it returns "Not scanned" (Target/Type = `-`), which is NOT the same as "0 findings". Use `trivy image` or `trivy rootfs` for embedded-Go-stdlib CVE detection. The analyzer only inspects executable-mode files (a `curl -o` download is 0644 → chmod +x first).
- **`go install pkg@version` cross-compile output path.** When `GOOS/GOARCH` differ from the build host, the binary lands in `$GOPATH/bin/${GOOS}_${GOARCH}/` (arch subdir), NOT `$GOPATH/bin/`. And `GOBIN` cannot be set for cross-compiled installs ("cannot install cross-compiled binaries when GOBIN is set"). Normalize: `cp "/go/bin/${TARGETOS}_${TARGETARCH}/x" /out 2>/dev/null || cp /go/bin/x /out`. This is why a per-target QEMU build keeps a simple `COPY /go/bin/x` path while `--platform=$BUILDPLATFORM` cross-compile needs the subdir dance.
- **buildx on this macOS** fails to read a Dockerfile placed under `/private/tmp`: `error from sender: failed to xattr /private/tmp/mdmdownloads: permission denied` (MDM-protected path). Put throwaway Dockerfiles INSIDE the repo dir and build with `-f Dockerfile.x .`.
- **`docker create --name`** rejects names starting with `_` ("Invalid container name").
- **Backgrounded `docker build ... ; echo exit $?`** reports the `echo`'s success even when the build ERRORed — read the build log, not the exit marker. See [[backgrounded_commit_exit_code_masks_failure]].

Domain facts worth reusing:
- **Debian backports CVE fixes without bumping upstream version.** openssl fix is 3.5.7 upstream but ships in trixie as `3.5.6-1~deb13u2` (the `debNuM` suffix IS the fixed marker). Trivy matches Debian security metadata, so a version claim citing `deb13u2` is correct even though it's "still 3.5.6".
- **The release Trivy gate lives ONLY in `release-please.yml`** (`build-and-push`, gated `if: release_created`); regular `ci.yml` never builds/scans the image. So green PR CI does NOT exercise an image-CVE fix, and the gate's first real run is the release itself — reproduce locally. Related: [[reference_release_jobs_invisible_to_pr_ci]].
- **Local Trivy DB may be newer than `trivy-action`'s bundled binary** — note the version delta when reproducing counts (finding totals drift as CVEs get fixed-upstream/reclassified; direction and specific CVE IDs are the stable signal).
