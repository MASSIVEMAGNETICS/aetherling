"""
Central constants for the 24-hour demo runtime.
"""

# Total window for the demo session (seconds).
DEMO_DURATION_SECONDS: int = 86_400  # 24 hours

# How often a new scenario is executed within the demo window (seconds).
SCENARIO_INTERVAL_SECONDS: int = 3_600  # 1 hour

# HMAC algorithm used for session-token signing.
HMAC_ALGORITHM: str = "sha256"

# Size of the HMAC signing key in bytes (256-bit key).
HMAC_KEY_SIZE: int = 32
