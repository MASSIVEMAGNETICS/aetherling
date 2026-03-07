"""
24hr_demo/config.py
-------------------
Configuration constants for the 24-hour demo runtime.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

#: Total demo window in seconds (24 hours).
DEMO_DURATION_SECONDS: int = 86_400

#: How often (in seconds) the demo scheduler fires a new scenario cycle.
SCENARIO_INTERVAL_SECONDS: int = 3_600  # every hour

#: Grace period (seconds) before the session token is considered expired.
TOKEN_CLOCK_SKEW_SECONDS: int = 30

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

#: Minimum entropy bytes for the session secret key.
SECRET_KEY_BYTES: int = 32

#: HMAC digest algorithm used for session tokens.
HMAC_ALGORITHM: str = "sha256"

#: Environment variable name that, when set, overrides the generated secret key.
SECRET_KEY_ENV_VAR: str = "DEMO_SECRET_KEY"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

#: Log format string.
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s – %(message)s"

#: Log date format.
LOG_DATE_FORMAT: str = "%Y-%m-%dT%H:%M:%S"
