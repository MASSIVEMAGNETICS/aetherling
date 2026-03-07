"""
24hr_demo/runtime.py
--------------------
Secure timed 24-hour demo runtime for the Aetherling platform.

Architecture overview
~~~~~~~~~~~~~~~~~~~~~
::

    DemoRuntime
    ├── _secret_key          – HMAC signing key (bytes)
    ├── _session_token       – Signed 24-hr expiry token (str)
    ├── _agent               – Aetherling (or StubAetherling) instance
    ├── _scheduler_thread    – Background thread firing hourly scenario cycles
    └── _status              – Live status dict updated after every cycle

Public API
~~~~~~~~~~
- :meth:`start`  – validate token, launch scheduler, begin demo.
- :meth:`stop`   – gracefully shut down scheduler.
- :meth:`status` – return a snapshot of the current demo state.

Security model
~~~~~~~~~~~~~~
1. A fresh HMAC-SHA-256 session token is minted at construction time.
2. :meth:`start` validates the token before allowing any scenario to run.
3. The scheduler continuously re-validates the token before every cycle;
   if the token has expired the runtime stops automatically.
4. No sensitive data (API keys, PII) is logged.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

from .config import (
    DEMO_DURATION_SECONDS,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    SCENARIO_INTERVAL_SECONDS,
)
from .demo_scenarios import SCENARIOS, StubAetherling, get_scenario_cycle
from .security import (
    create_session_token,
    load_or_generate_secret_key,
    seconds_remaining,
    validate_session_token,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger("24hr_demo.runtime")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


class DemoRuntime:
    """Secure timed demo runtime.

    Parameters
    ----------
    agent:
        An Aetherling (or compatible) instance to exercise during the demo.
        If ``None`` a :class:`~demo_scenarios.StubAetherling` is used so the
        demo runs without external dependencies.
    secret_key:
        Raw bytes for HMAC signing.  If ``None``,
        :func:`~security.load_or_generate_secret_key` is called.
    scenario_interval:
        Seconds between scenario cycles.  Defaults to
        :data:`~config.SCENARIO_INTERVAL_SECONDS` (3600 s / 1 hour).
    demo_duration:
        Total demo window in seconds.  Defaults to
        :data:`~config.DEMO_DURATION_SECONDS` (86400 s / 24 hours).
    """

    def __init__(
        self,
        agent: Optional[Any] = None,
        secret_key: Optional[bytes] = None,
        scenario_interval: int = SCENARIO_INTERVAL_SECONDS,
        demo_duration: int = DEMO_DURATION_SECONDS,
    ) -> None:
        self._agent: Any = agent or StubAetherling()
        self._secret_key: bytes = secret_key or load_or_generate_secret_key()
        self._scenario_interval: int = scenario_interval
        self._demo_duration: int = demo_duration

        # Mint the session token immediately
        self._session_token: str = create_session_token(
            self._secret_key, duration_seconds=self._demo_duration
        )

        self._stop_event: threading.Event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

        self._status: Dict[str, Any] = {
            "state": "initialised",
            "cycles_completed": 0,
            "last_cycle_results": [],
            "session_valid": True,
            "seconds_remaining": float(self._demo_duration),
        }

        logger.info(
            "DemoRuntime initialised – demo window=%ds  interval=%ds  agent=%s",
            self._demo_duration,
            self._scenario_interval,
            type(self._agent).__name__,
        )

    # ---------------------------------------------------------------------- #
    # Public interface
    # ---------------------------------------------------------------------- #

    @property
    def session_token(self) -> str:
        """The signed session token for this demo run (read-only)."""
        return self._session_token

    def start(self) -> None:
        """Validate the session token and launch the background scheduler.

        Raises
        ------
        PermissionError
            If the session token fails validation (tampered or expired).
        RuntimeError
            If the runtime has already been started.
        """
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            raise RuntimeError("DemoRuntime is already running.")

        if not validate_session_token(self._session_token, self._secret_key):
            raise PermissionError(
                "Session token is invalid or has expired.  "
                "Create a new DemoRuntime to obtain a fresh token."
            )

        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="demo-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()

        with self._lock:
            self._status["state"] = "running"

        logger.info("DemoRuntime started – session token validated ✓")

    def stop(self) -> None:
        """Gracefully stop the demo scheduler."""
        self._stop_event.set()
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=10)

        with self._lock:
            self._status["state"] = "stopped"

        logger.info("DemoRuntime stopped.")

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of the current demo state.

        Returns
        -------
        dict
            Contains:

            - ``state`` – ``"initialised"`` | ``"running"`` | ``"stopped"`` | ``"expired"``
            - ``cycles_completed`` – number of scenario cycles finished so far.
            - ``last_cycle_results`` – list of result strings from the last cycle.
            - ``session_valid`` – whether the session token is still valid.
            - ``seconds_remaining`` – approximate seconds left in the demo window.
        """
        secs = seconds_remaining(self._session_token, self._secret_key) or 0.0
        valid = validate_session_token(self._session_token, self._secret_key)

        with self._lock:
            snapshot = dict(self._status)
            snapshot["session_valid"] = valid
            snapshot["seconds_remaining"] = max(0.0, secs)

        return snapshot

    # ---------------------------------------------------------------------- #
    # Internal scheduler
    # ---------------------------------------------------------------------- #

    def _run_cycle(self, hour: int) -> None:
        """Execute one scenario cycle for the given *hour* index."""
        scenarios = get_scenario_cycle(hour)
        results = []

        logger.info("── Cycle hour=%d  running %d scenario(s) ──", hour, len(scenarios))

        for scenario in scenarios:
            try:
                result = scenario.run(self._agent)
                logger.info("  [%s] %s", scenario.name, result)
                results.append({"scenario": scenario.name, "result": result, "ok": True})
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                logger.warning("  [%s] ERROR – %s", scenario.name, msg)
                results.append({"scenario": scenario.name, "result": msg, "ok": False})

        with self._lock:
            self._status["cycles_completed"] += 1
            self._status["last_cycle_results"] = results

    def _scheduler_loop(self) -> None:
        """Background loop: fire a scenario cycle every interval until stopped/expired."""
        hour = 0
        deadline = time.time() + self._demo_duration

        while not self._stop_event.is_set():
            # Security gate: re-validate token before every cycle
            if not validate_session_token(self._session_token, self._secret_key):
                logger.warning(
                    "Session token has expired or been invalidated – stopping runtime."
                )
                with self._lock:
                    self._status["state"] = "expired"
                    self._status["session_valid"] = False
                break

            if time.time() >= deadline:
                logger.info("Demo window of %d seconds has elapsed – stopping.", self._demo_duration)
                with self._lock:
                    self._status["state"] = "stopped"
                break

            self._run_cycle(hour)
            hour += 1

            # Sleep in small increments so stop_event is checked promptly
            interval_end = time.monotonic() + self._scenario_interval
            while not self._stop_event.is_set():
                remaining = interval_end - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(1.0, remaining))

        logger.info("Scheduler loop exited.")
