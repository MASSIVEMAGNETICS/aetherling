# 24hr\_demo – Secure Timed 24-Hour Demo Runtime

A self-contained subfolder that provides a **secure, timed full demo** of the
Aetherling platform running for a 24-hour window.

---

## Overview

| Component | Purpose |
|-----------|---------|
| `config.py` | Centralised timing and security constants |
| `security.py` | HMAC-SHA-256 session-token creation and validation |
| `demo_scenarios.py` | Six demo scenarios exercising every core capability |
| `runtime.py` | Threaded scheduler that gates execution on a valid token |
| `run_demo.py` | CLI entry-point with signal handling |
| `__init__.py` | Public package surface |

---

## Quick Start

```bash
# From the repository root

# Run the full 24-hour demo (blocks until complete or Ctrl-C):
python -m 24hr_demo.run_demo

# Short smoke-test (60-second window, 10-second cycles):
python -m 24hr_demo.run_demo --duration 60 --interval 10

# Print the session token and exit immediately:
python -m 24hr_demo.run_demo --token-only
```

---

## Security Model

### Session Tokens

A demo session token is an **HMAC-SHA-256**-signed, URL-safe base64 string
that encodes an expiry timestamp:

```
base64url( "<unix_expiry>.<hmac_hex_digest>" )
```

Key properties:

* **Stateless** – no database required; the expiry is embedded in the token.
* **Tamper-evident** – any modification invalidates the HMAC signature.
* **Constant-time comparison** – `hmac.compare_digest` prevents timing attacks.
* **No PII** – the token only grants time-bounded access; it carries no user
  identity or sensitive data.

### Secret Key

On first run a 32-byte cryptographically random key is generated and its hex
representation is printed:

```
[demo-security] Generated new secret key – set DEMO_SECRET_KEY=<hex> to reuse across restarts.
```

To persist the key across restarts export the environment variable:

```bash
export DEMO_SECRET_KEY=<hex_from_above>
```

### Runtime Security Gates

1. `DemoRuntime.start()` validates the session token **before** any scenario
   runs. If the token is invalid or expired a `PermissionError` is raised.
2. The background scheduler **re-validates the token before every cycle**.
   If it has expired the runtime transitions to `"expired"` state and exits.
3. Scenarios that raise unexpected exceptions are caught, logged as warnings,
   and do **not** crash the runtime.

---

## Demo Scenarios

| # | Name | Description |
|---|------|-------------|
| 1 | `perception` | Exercise `perceive_and_act` lifecycle method |
| 2 | `dream_mutation` | Trigger `dream_and_mutate` evolution cycle |
| 3 | `constitution_check` | Verify harmful mutations are rejected |
| 4 | `memory_store_retrieve` | Round-trip an experience through `FractalCognitiveSubstrate` |
| 5 | `soul_token_integrity` | Assert the soul token is stable and non-empty |
| 6 | `add_guardrail` | Add a runtime guardrail and confirm it persists |

**Cycle schedule:**

- **Hour 0** – all 6 scenarios run.
- **Hours 1–22** – one scenario per hour (rotating).
- **Hour 23** – all 6 scenarios run again for a final validation sweep.

---

## Without Full Dependencies

If the `aetherling` package is not installed, the runtime automatically falls
back to `StubAetherling` – a minimal stand-in that replicates the public API
so every scenario code path can still be exercised.

---

## Status API

```python
from 24hr_demo import DemoRuntime

runtime = DemoRuntime(scenario_interval=10, demo_duration=60)
runtime.start()

snap = runtime.status()
# {
#   "state": "running",
#   "cycles_completed": 1,
#   "last_cycle_results": [...],
#   "session_valid": True,
#   "seconds_remaining": 45.3,
# }

runtime.stop()
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_SECRET_KEY` | *(auto-generated)* | Hex-encoded 32-byte HMAC signing key |
