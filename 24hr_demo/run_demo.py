"""
24hr_demo/run_demo.py
---------------------
CLI entry-point for the secure 24-hour Aetherling demo runtime.

Usage
-----
::

    # Run the full 24-hour demo (blocks until complete or Ctrl-C):
    python 24hr_demo/run_demo.py

    # Run a short smoke-test (60-second window, 10-second cycles):
    python 24hr_demo/run_demo.py --duration 60 --interval 10

    # Print the generated session token and exit without running:
    python 24hr_demo/run_demo.py --token-only

Environment variables
---------------------
``DEMO_SECRET_KEY``
    Hex-encoded 32-byte secret key.  If unset a fresh key is generated and
    printed at startup.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

from .runtime import DemoRuntime
from .config import DEMO_DURATION_SECONDS, SCENARIO_INTERVAL_SECONDS


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_demo",
        description="Secure timed 24-hour Aetherling demo runtime.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEMO_DURATION_SECONDS,
        metavar="SECONDS",
        help="Total demo window in seconds.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=SCENARIO_INTERVAL_SECONDS,
        metavar="SECONDS",
        help="Seconds between scenario cycles.",
    )
    parser.add_argument(
        "--token-only",
        action="store_true",
        help="Print the session token and exit without running the demo.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry-point; returns an exit code."""
    args = _parse_args(argv)

    runtime = DemoRuntime(
        scenario_interval=args.interval,
        demo_duration=args.duration,
    )

    if args.token_only:
        print(runtime.session_token)
        return 0

    # Register signal handlers for clean shutdown
    def _signal_handler(sig: int, _frame: object) -> None:  # noqa: ARG001
        print(f"\n[run_demo] Received signal {sig} – stopping runtime…", flush=True)
        runtime.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print(f"[run_demo] Session token: {runtime.session_token}")
    print(
        f"[run_demo] Starting demo – duration={args.duration}s  interval={args.interval}s"
    )

    runtime.start()

    try:
        while True:
            snap = runtime.status()
            if snap["state"] != "running":
                print(f"[run_demo] Runtime state is '{snap['state']}' – exiting.")
                break
            print(
                f"[run_demo] status – cycles={snap['cycles_completed']}  "
                f"remaining={snap['seconds_remaining']:.0f}s  "
                f"token_valid={snap['session_valid']}",
                flush=True,
            )
            time.sleep(min(30, args.interval))
    finally:
        runtime.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
