"""
24hr_demo/security.py
---------------------
HMAC-based session-token utilities for the 24-hour demo runtime.

A *demo session token* is a URL-safe, base64-encoded string that encodes:

    ``<expiry_unix_ts>.<hmac_hex_digest>``

The HMAC is computed over ``<expiry_unix_ts>`` using a secret key that is
either loaded from the environment variable ``DEMO_SECRET_KEY`` or generated
fresh at startup with :func:`generate_secret_key`.

Design decisions
~~~~~~~~~~~~~~~~
* **HMAC-SHA-256** – widely supported, constant-time comparison via
  :func:`hmac.compare_digest`.
* **Expiry embedded in the token** – stateless validation; no database needed.
* **No user-identifiable data** – the token only authorises *time-bounded*
  access to the demo runtime, satisfying minimal-privilege principles.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from .config import (
    DEMO_DURATION_SECONDS,
    HMAC_ALGORITHM,
    SECRET_KEY_BYTES,
    SECRET_KEY_ENV_VAR,
    TOKEN_CLOCK_SKEW_SECONDS,
)


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


def generate_secret_key() -> bytes:
    """Return a cryptographically random secret key.

    The key is :data:`~config.SECRET_KEY_BYTES` bytes long.
    """
    return secrets.token_bytes(SECRET_KEY_BYTES)


def load_or_generate_secret_key() -> bytes:
    """Return the secret key from the environment, or generate a fresh one.

    If :envvar:`DEMO_SECRET_KEY` is set it is decoded from hex; otherwise a
    new random key is generated and its hex representation is printed to
    stdout so the operator can record it.
    """
    raw = os.environ.get(SECRET_KEY_ENV_VAR, "")
    if raw:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            import warnings
            warnings.warn(
                f"Environment variable {SECRET_KEY_ENV_VAR!r} contains an invalid hex "
                "value and will be ignored.  A fresh key has been generated instead.",
                stacklevel=2,
            )

    key = generate_secret_key()
    print(
        f"[demo-security] Generated new secret key – set "
        f"{SECRET_KEY_ENV_VAR}={key.hex()} to reuse across restarts."
    )
    return key


# ---------------------------------------------------------------------------
# Token creation & validation
# ---------------------------------------------------------------------------


def _sign(expiry: int, secret_key: bytes) -> str:
    """Return the HMAC-SHA-256 hex digest of the expiry timestamp."""
    msg = str(expiry).encode("utf-8")
    return hmac.new(secret_key, msg, digestmod=HMAC_ALGORITHM).hexdigest()


def create_session_token(
    secret_key: bytes,
    duration_seconds: int = DEMO_DURATION_SECONDS,
) -> str:
    """Create a signed session token valid for *duration_seconds*.

    Parameters
    ----------
    secret_key:
        The HMAC signing key (raw bytes).
    duration_seconds:
        How long (in seconds from now) the token should remain valid.
        Defaults to :data:`~config.DEMO_DURATION_SECONDS` (24 hours).

    Returns
    -------
    str
        A URL-safe base64-encoded token string.
    """
    if not secret_key:
        raise ValueError(
            "secret_key must be non-empty bytes. "
            "Use load_or_generate_secret_key() to obtain a valid key."
        )
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive.")

    expiry = int(time.time()) + duration_seconds
    signature = _sign(expiry, secret_key)
    raw = f"{expiry}.{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def validate_session_token(
    token: str,
    secret_key: bytes,
    clock_skew: int = TOKEN_CLOCK_SKEW_SECONDS,
) -> bool:
    """Validate a session token.

    Parameters
    ----------
    token:
        The token string previously returned by :func:`create_session_token`.
    secret_key:
        The HMAC signing key (raw bytes).
    clock_skew:
        Number of seconds of leniency when comparing the current time to the
        token's expiry timestamp.

    Returns
    -------
    bool
        ``True`` if the token has a valid signature **and** has not expired.
    """
    if not token or not secret_key:
        return False

    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        parts = raw.decode("utf-8").split(".", 1)
        if len(parts) != 2:
            return False

        expiry = int(parts[0])
        provided_sig = parts[1]
    except Exception:
        return False

    expected_sig = _sign(expiry, secret_key)
    if not hmac.compare_digest(expected_sig, provided_sig):
        return False

    if time.time() > expiry + clock_skew:
        return False

    return True


def seconds_remaining(token: str, secret_key: bytes) -> Optional[float]:
    """Return the number of seconds until the token expires, or ``None`` if invalid.

    Parameters
    ----------
    token:
        A token previously returned by :func:`create_session_token`.
    secret_key:
        The HMAC signing key.

    Returns
    -------
    float | None
        Remaining seconds (may be negative if already expired), or ``None``
        if the token cannot be decoded or its signature is invalid.
    """
    if not token or not secret_key:
        return None

    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        parts = raw.decode("utf-8").split(".", 1)
        if len(parts) != 2:
            return None

        expiry = int(parts[0])
        provided_sig = parts[1]
    except Exception:
        return None

    expected_sig = _sign(expiry, secret_key)
    if not hmac.compare_digest(expected_sig, provided_sig):
        return None

    return float(expiry) - time.time()
