"""
HMAC-SHA-256 session-token utilities for the 24-hour demo runtime.

Token format
------------
``<base64url(payload_json)>.<base64url(hmac_signature)>``

The JSON payload contains:

* ``iat`` – issued-at Unix timestamp (int)
* ``exp`` – expiry Unix timestamp (int)

Security properties
-------------------
* Stateless – the server needs only the signing key to validate a token.
* Constant-time comparison via :func:`hmac.compare_digest`.
* Key is loaded from the ``AETHERLING_DEMO_KEY`` environment variable
  (hex-encoded, 32 bytes / 64 hex characters).  If the variable is absent or
  carries an invalid value a warning is emitted and a fresh ephemeral key is
  used for the current process only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import warnings
from typing import Optional

try:
    from .config import HMAC_ALGORITHM, HMAC_KEY_SIZE
except ImportError:
    from config import HMAC_ALGORITHM, HMAC_KEY_SIZE  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

_ENV_KEY_VAR = "AETHERLING_DEMO_KEY"


def _load_key() -> bytes:
    """Load the signing key from the environment or generate an ephemeral one."""
    raw = os.environ.get(_ENV_KEY_VAR, "")
    if raw:
        try:
            key = bytes.fromhex(raw)
            if len(key) != HMAC_KEY_SIZE:
                raise ValueError(
                    f"Key must be exactly {HMAC_KEY_SIZE} bytes "
                    f"({HMAC_KEY_SIZE * 2} hex chars); got {len(key)}."
                )
            return key
        except (ValueError, TypeError) as exc:
            warnings.warn(
                f"{_ENV_KEY_VAR} contains an invalid value ({exc}). "
                "Falling back to an ephemeral key – tokens will not persist "
                "across process restarts.",
                stacklevel=2,
            )
    # Ephemeral key – valid only for this process lifetime.
    return secrets.token_bytes(HMAC_KEY_SIZE)


# Module-level key, resolved once at import time.
_SIGNING_KEY: bytes = _load_key()


# ---------------------------------------------------------------------------
# Base64url helpers (no padding)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    padding = 4 - len(text) % 4
    if padding != 4:
        text += "=" * padding
    return base64.urlsafe_b64decode(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_token(duration_seconds: int, *, key: Optional[bytes] = None) -> str:
    """Create a signed session token valid for *duration_seconds* seconds.

    Parameters
    ----------
    duration_seconds:
        Number of seconds from now until the token expires.
    key:
        Optional override signing key (bytes).  Defaults to the module-level
        key loaded from :data:`AETHERLING_DEMO_KEY`.

    Returns
    -------
    str
        URL-safe token string in ``<payload>.<signature>`` format.
    """
    signing_key = key if key is not None else _SIGNING_KEY
    now = int(time.time())
    payload = json.dumps({"iat": now, "exp": now + duration_seconds}, separators=(",", ":"))
    payload_b64 = _b64url_encode(payload.encode())
    sig = hmac.new(signing_key, payload_b64.encode(), HMAC_ALGORITHM).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def validate_token(token: str, *, key: Optional[bytes] = None) -> bool:
    """Return ``True`` if *token* is structurally valid and not expired.

    Performs a constant-time HMAC comparison to prevent timing attacks.

    Parameters
    ----------
    token:
        Token string previously produced by :func:`generate_token`.
    key:
        Optional override signing key.  Must match the key used at generation
        time.

    Returns
    -------
    bool
        ``True`` when the token is valid and the current time is within the
        ``iat``–``exp`` window.
    """
    signing_key = key if key is not None else _SIGNING_KEY
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        payload_b64, sig_b64 = parts

        # Recompute expected signature
        expected_sig = hmac.new(signing_key, payload_b64.encode(), HMAC_ALGORITHM).digest()
        provided_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, provided_sig):
            return False

        # Decode payload and check expiry
        payload = json.loads(_b64url_decode(payload_b64))
        exp = payload.get("exp")
        if exp is None or time.time() > exp:
            return False

        return True
    except Exception:  # noqa: BLE001
        return False


def token_expiry(token: str) -> Optional[int]:
    """Return the ``exp`` Unix timestamp embedded in *token*, or ``None``.

    Does **not** validate the token signature.  Use :func:`validate_token`
    for security decisions.
    """
    try:
        payload_b64 = token.split(".")[0]
        payload = json.loads(_b64url_decode(payload_b64))
        return int(payload["exp"])
    except Exception:  # noqa: BLE001
        return None
