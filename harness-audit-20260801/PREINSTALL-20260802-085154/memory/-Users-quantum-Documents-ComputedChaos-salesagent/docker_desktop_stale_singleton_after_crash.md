---
name: docker-desktop-stale-singleton-after-crash
description: "After a power loss/hard crash, Docker Desktop won't launch — open -a spawns nothing, backend dies with \"unmarshaling start request: unexpected EOF\". Fix = delete stale Electron Singleton* files."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 57bf7c0c-9125-495a-9010-e6e18f965fee
---

After a hard crash (power loss), `open -a Docker` exits 0 but spawns NO processes, and `backend.error.json` / direct `com.docker.backend` runs show `unmarshaling start request: unexpected EOF` in Electron `doOpen` plus cascading fork/exec EOF failures.

**Root cause:** stale Electron singleton lock from the pre-crash instance: `~/Library/Application Support/Docker Desktop/SingletonLock` (symlink → `<host>-<dead pid>`) and `SingletonSocket` (→ reboot-cleared `/var/folders/...` temp dir). New instances see a "running" app, try to hand off via the dead socket, and exit silently.

**Fix:**
```bash
rm -f ~/Library/Application\ Support/Docker\ Desktop/Singleton{Cookie,Lock,Socket}
open -a Docker
```
Deleting `~/Library/Containers/com.docker.docker/backend.lock` / `backend.error.json` alone does NOT fix it. VM data (`Data/`) is untouched by this fix. Check staleness via `ls -la` dates on the Singleton symlinks vs last boot.
