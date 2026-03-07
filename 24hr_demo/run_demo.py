#!/usr/bin/env python3
"""
CLI entry-point for the 24-hour Aetherling demo.

Usage
-----
::

    # Generate a token and print it, then exit:
    python run_demo.py --token-only

    # Run the full 24-hour demo with default settings:
    python run_demo.py --token <TOKEN>

    # Run a short smoke-test (60 s demo, 10 s interval):
    python run_demo.py --token <TOKEN> --duration 60 --interval 10

Options
-------
--token TOKEN       Session token (from a previous --token-only run).
                    If omitted a fresh token is generated automatically.
--duration SECONDS  Override the demo window (default: 86400).
--interval SECONDS  Override the scenario interval (default: 3600).
--token-only        Print a freshly generated token and exit immediately.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import List, Optional

# Allow running as a script from within the 24hr_demo folder or from the repo
# root without installing the package.
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REPO_ROOT = _os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import DEMO_DURATION_SECONDS, SCENARIO_INTERVAL_SECONDS  # noqa: E402
from security import generate_token, validate_token  # noqa: E402
from runtime import DemoRuntime  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("run_demo")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_demo.py",
        description="24-hour HMAC-secured Aetherling demo runtime.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help=(
            "Session token produced by a previous --token-only invocation.  "
            "A new token is generated automatically when this flag is omitted."
        ),
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=DEMO_DURATION_SECONDS,
        metavar="SECONDS",
        help=f"Total demo window in seconds (default: {DEMO_DURATION_SECONDS}).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=SCENARIO_INTERVAL_SECONDS,
        metavar="SECONDS",
        help=f"Scenario interval in seconds (default: {SCENARIO_INTERVAL_SECONDS}).",
    )
    parser.add_argument(
        "--token-only",
        action="store_true",
        dest="token_only",
        help="Print a freshly generated session token and exit immediately.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # ── Token-only mode ───────────────────────────────────────────────────
    if args.token_only:
        token = generate_token(args.duration)
        print(token)
        return 0

    # ── Resolve or generate the session token ─────────────────────────────
    if args.token:
        token = args.token
        if not validate_token(token):
            logger.error("Provided token is invalid or has already expired.")
            return 1
    else:
        token = generate_token(args.duration)
        logger.info("Generated session token: %s", token)

    # ── Launch the runtime ────────────────────────────────────────────────
    runtime = DemoRuntime(
        token=token,
        duration_seconds=args.duration,
        interval_seconds=args.interval,
        on_scenario=lambda r: logger.info(
            "  → scenario=%r passed=%r detail=%r",
            r.get("scenario"),
            r.get("passed"),
            r.get("detail"),
        ),
    )

    # ── Signal handling (SIGINT / SIGTERM) ────────────────────────────────
    def _handle_signal(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s – requesting graceful shutdown …", sig_name)
        runtime.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        runtime.start()
        logger.info(
            "Demo running for %d s (interval %d s).  Press Ctrl-C to stop.",
            args.duration,
            args.interval,
        )
        runtime.join()
    except ValueError as exc:
        logger.error("Failed to start runtime: %s", exc)
        return 1

    results = runtime.results
    passed = sum(1 for r in results if r.get("passed"))
    logger.info(
        "Demo finished. %d/%d scenarios passed.", passed, len(results)
    )
    return 0 if len(results) == 0 or passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
