---
name: reference_httpx_ssrf_ip_pinning
description: "Safe SSRF IP-pinning with httpx — sni_hostname bypasses cert verification; pin via httpcore's _network_backend instead"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 77235ac6-73c5-488a-99a2-0abb0f51ef4a
---

To close an SSRF DNS-rebinding TOCTOU on an httpx fetch (validate-then-connect re-resolves; a rebinding host passes validation on a public A-record then connects to a private IP), the connection must be PINNED to the already-validated IP. Two mechanisms — only one is safe (verified empirically, httpx 0.28.1 / httpcore 1.0.9):

- **UNSAFE — the `sni_hostname` request extension.** Putting the IP in the URL + `headers={"Host": host}` + `extensions={"sni_hostname": host}` connects to the IP but does NOT verify the cert against the hostname — a *wrong* `sni_hostname` still connects. It silently disables hostname verification. Never use it for a security pin.
- **SAFE — override httpcore's private network backend.** Keep the request URL on the HOSTNAME (so httpx's normal TLS SNI + cert-hostname verification run — a wrong/rebound IP whose cert doesn't match FAILS with `CERTIFICATE_VERIFY_FAILED: Hostname mismatch`), and pin only the TCP connect target:
  ```python
  from httpcore._backends.sync import SyncBackend      # async: httpcore._backends.anyio.AnyIOBackend
  class _Pinned(SyncBackend):
      def __init__(self, ip): self._ip = ip
      def connect_tcp(self, host, port, *a, **k): return super().connect_tcp(self._ip, port, *a, **k)
  t = httpx.HTTPTransport(); t._pool._network_backend = _Pinned(validated_ip)  # async: AsyncHTTPTransport
  ```
  Also validate EVERY `socket.getaddrinfo` address (not just `gethostbyname`'s first result) — closes the multi-A-record bypass.

`_pool._network_backend` and `httpcore._backends` are PRIVATE (version-fragile). Guard the pin with a failing oracle: drive a real httpx request through the pinned transport with the backend's `connect_tcp` spied, and assert it targets the validated IP, not the request hostname — so an httpcore-internals change reddens rather than silently reopening the hole ([[feedback_claimed_invariant_needs_failing_oracle]]). In salesagent this lives in `src/core/security/url_validator.py` (`resolve_validated_ip`, `ssrf_pinned_transport`/`_async`), used by `property_list_resolver`. See [[feedback_verify_remedy_before_public_post]] — a TLS-touching security fix must be empirically verified (right IP connects, wrong IP fails verification), never shipped on assumption.
