"""
DemoRuntime – threaded scheduler for the 24-hour Aetherling demo.

Lifecycle
---------
1. :meth:`DemoRuntime.start` validates the session token, then launches a
   background thread that fires every ``interval_seconds``.
2. Before each hourly cycle the token is revalidated.  If it has expired or
   been invalidated the runtime stops automatically.
3. :meth:`DemoRuntime.stop` can be called at any time (e.g. from a signal
   handler) to request a clean shutdown.
4. The runtime also auto-stops when the ``duration_seconds`` window elapses.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from .config import DEMO_DURATION_SECONDS, SCENARIO_INTERVAL_SECONDS
    from .security import validate_token
except ImportError:
    from config import DEMO_DURATION_SECONDS, SCENARIO_INTERVAL_SECONDS  # type: ignore[no-redef]
    from security import validate_token  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


class DemoRuntime:
    """Threaded demo scheduler.

    Parameters
    ----------
    token:
        A session token produced by :func:`~demo.security.generate_token`.
        The token is validated at :meth:`start` and before each interval
        tick.
    duration_seconds:
        Total window for the demo.  Defaults to
        :data:`~demo.config.DEMO_DURATION_SECONDS` (86 400 s / 24 hours).
    interval_seconds:
        How often to execute the next scenario.  Defaults to
        :data:`~demo.config.SCENARIO_INTERVAL_SECONDS` (3 600 s / 1 hour).
    on_scenario:
        Optional callback invoked after each scenario cycle with the
        scenario result dict.  Useful for logging or metrics.
    """

    def __init__(
        self,
        token: str,
        *,
        key: Optional[bytes] = None,
        duration_seconds: int = DEMO_DURATION_SECONDS,
        interval_seconds: int = SCENARIO_INTERVAL_SECONDS,
        on_scenario: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self._token = token
        self._key = key
        self._duration = duration_seconds
        self._interval = interval_seconds
        self._on_scenario = on_scenario

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._results: List[Dict[str, Any]] = []
        self._running = False

    # ---------------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------------- #

    def start(self) -> None:
        """Validate the token and launch the background scheduler.

        Raises
        ------
        ValueError
            If the token is invalid or already expired at call time.
        RuntimeError
            If the runtime is already running.
        """
        if self._running:
            raise RuntimeError("DemoRuntime is already running.")
        if not validate_token(self._token, key=self._key):
            raise ValueError(
                "Cannot start DemoRuntime: session token is invalid or expired."
            )
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="DemoRuntime-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "DemoRuntime started (duration=%ds, interval=%ds).",
            self._duration,
            self._interval,
        )

    def stop(self) -> None:
        """Signal the background scheduler to stop after the current cycle."""
        self._stop_event.set()
        logger.info("DemoRuntime stop requested.")

    def join(self, timeout: Optional[float] = None) -> None:
        """Block until the background thread has finished.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait.  Passes through to
            :meth:`threading.Thread.join`.
        """
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        """``True`` while the background scheduler thread is alive."""
        return self._running and (
            self._thread is not None and self._thread.is_alive()
        )

    @property
    def results(self) -> List[Dict[str, Any]]:
        """Read-only snapshot of scenario results collected so far."""
        return list(self._results)

    # ---------------------------------------------------------------------- #
    # Internal scheduler loop
    # ---------------------------------------------------------------------- #

    def _run_loop(self) -> None:
        """Background thread target: execute scenarios at each interval."""
        try:
            from .demo_scenarios import ALL_SCENARIOS, StubAetherling
        except ImportError:
            from demo_scenarios import ALL_SCENARIOS, StubAetherling  # type: ignore[no-redef]

        agent = StubAetherling(
            dna_config={
                "soul_token": "demo-runtime-agent",
                "guardrails": ["Never impersonate a human."],
            },
            genesis_prompt="You are a 24-hour demo runtime agent.",
        )
        scenario_iter = iter(ALL_SCENARIOS)
        deadline = time.monotonic() + self._duration

        try:
            while not self._stop_event.is_set():
                # Auto-stop when the demo window expires
                if time.monotonic() >= deadline:
                    logger.info("DemoRuntime: demo window expired – stopping.")
                    break

                # Revalidate the token before each cycle
                if not validate_token(self._token, key=self._key):
                    logger.warning(
                        "DemoRuntime: token invalidated or expired – stopping."
                    )
                    break

                # Run next scenario (cycle back to start when exhausted)
                try:
                    fn = next(scenario_iter)
                except StopIteration:
                    scenario_iter = iter(ALL_SCENARIOS)
                    fn = next(scenario_iter)

                result = fn(agent)
                self._results.append(result)
                status = "PASS" if result.get("passed") else "FAIL"
                logger.info(
                    "Scenario %r: %s – %s",
                    result.get("scenario"),
                    status,
                    result.get("detail", ""),
                )
                if self._on_scenario is not None:
                    try:
                        self._on_scenario(result)
                    except Exception:  # noqa: BLE001
                        logger.exception("on_scenario callback raised an error.")

                # Wait for the next interval (or stop if signalled)
                self._stop_event.wait(timeout=self._interval)
        finally:
            self._running = False
            logger.info("DemoRuntime scheduler thread exiting.")
