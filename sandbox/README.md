# Sandbox Runtime

This directory contains a hardened Docker setup used by the `python` tool for executing untrusted or semi-trusted Python code.

Files:

- `secure_python.Dockerfile`: minimal runtime image.
- `secure_python_science.Dockerfile`: runtime image with pinned `numpy`, `sympy`, and `pandas`.
- `build_secure_python.sh`: builds `base` or `science` image.
- `run_secure_python.sh`: runs a script with hardened runtime flags.

## Build

Base image:

```bash
sandbox/build_secure_python.sh base
```

Science image:

```bash
sandbox/build_secure_python.sh science
```

## Why This Is Secure (Defense in Depth)

The runtime uses multiple controls together:

1. Process isolation: code runs in a separate container, not in the app process.
2. No network: `--network none` blocks outbound/inbound network access.
3. Non-root user: `--user 65534:65534` reduces privileges.
4. Read-only root FS: `--read-only` limits filesystem mutation.
5. Minimal writable temp space: `--tmpfs /tmp:...` confines temporary writes.
6. Dropped Linux capabilities: `--cap-drop=ALL` removes elevated kernel powers.
7. No privilege escalation: `--security-opt no-new-privileges`.
8. Resource limits: CPU, memory, pids, and ulimits reduce DoS impact.
9. Execution timeout: host-side timeout kills long-running code.
10. Static code checks in app: Python AST validation blocks some dangerous patterns before execution.

No single control is enough; the strength is the combination.

## Known Weaknesses / Residual Risks

1. Container != VM: container isolation is strong but not absolute.
2. Kernel/runtime vulnerabilities: escape risk exists if Docker/container runtime/host kernel has exploitable bugs.
3. Misconfiguration risk: weakening flags (network on, privileged mode, host mounts) can break assumptions.
4. Supply chain risk: installed Python packages can contain vulnerabilities.
5. DoS is reduced, not eliminated: tight limits help, but resource pressure is still possible.
6. Local file mount exposure: mounted script path is read-only, but still visible in container.

## Operational Guidance

1. Keep host OS, kernel, Docker Engine, and base images patched.
2. Do not run with `--privileged` and do not mount Docker socket.
3. Keep image dependencies minimal and pinned.
4. Use `secure-python` for general usage; use `secure-python-science` only when needed.
5. Periodically review runtime flags and limits as workloads change.
