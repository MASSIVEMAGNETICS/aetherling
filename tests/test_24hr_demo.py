"""
Tests for the 24hr_demo sub-package.

Covers:
* config constants
* security token generation and validation
* all six demo scenarios
* DemoRuntime lifecycle
"""

from __future__ import annotations

import sys
import os
import time

import pytest

# Make the 24hr_demo directory importable as a plain package
_DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "24hr_demo")
if _DEMO_DIR not in sys.path:
    sys.path.insert(0, _DEMO_DIR)

import config as demo_config  # noqa: E402
import security as demo_security  # noqa: E402
import demo_scenarios  # noqa: E402
from runtime import DemoRuntime  # noqa: E402


# ===========================================================================
# config
# ===========================================================================

class TestDemoConfig:
    def test_demo_duration(self):
        assert demo_config.DEMO_DURATION_SECONDS == 86_400

    def test_scenario_interval(self):
        assert demo_config.SCENARIO_INTERVAL_SECONDS == 3_600

    def test_hmac_algorithm(self):
        assert demo_config.HMAC_ALGORITHM == "sha256"

    def test_hmac_key_size(self):
        assert demo_config.HMAC_KEY_SIZE == 32


# ===========================================================================
# security
# ===========================================================================

@pytest.fixture()
def demo_key() -> bytes:
    """A fresh 32-byte signing key for each test."""
    import secrets
    return secrets.token_bytes(32)


class TestGenerateToken:
    def test_returns_string(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        assert isinstance(token, str)

    def test_token_has_two_parts(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        assert token.count(".") == 1

    def test_different_keys_produce_different_tokens(self):
        import secrets
        k1 = secrets.token_bytes(32)
        k2 = secrets.token_bytes(32)
        t1 = demo_security.generate_token(3600, key=k1)
        t2 = demo_security.generate_token(3600, key=k2)
        assert t1 != t2

    def test_different_durations_produce_different_tokens(self, demo_key):
        t1 = demo_security.generate_token(3600, key=demo_key)
        time.sleep(0.01)  # ensure different iat
        t2 = demo_security.generate_token(7200, key=demo_key)
        assert t1 != t2


class TestValidateToken:
    def test_valid_token_passes(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        assert demo_security.validate_token(token, key=demo_key)

    def test_wrong_key_fails(self, demo_key):
        import secrets
        token = demo_security.generate_token(3600, key=demo_key)
        other_key = secrets.token_bytes(32)
        assert not demo_security.validate_token(token, key=other_key)

    def test_expired_token_fails(self, demo_key):
        # Token valid for -1 s (already expired)
        token = demo_security.generate_token(-1, key=demo_key)
        assert not demo_security.validate_token(token, key=demo_key)

    def test_tampered_payload_fails(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        # Flip a character in the payload section
        payload_b64, sig_b64 = token.split(".")
        tampered = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B")
        bad_token = f"{tampered}.{sig_b64}"
        assert not demo_security.validate_token(bad_token, key=demo_key)

    def test_malformed_token_fails(self, demo_key):
        assert not demo_security.validate_token("not.a.valid.token.at.all", key=demo_key)
        assert not demo_security.validate_token("", key=demo_key)
        assert not demo_security.validate_token("nodot", key=demo_key)


class TestTokenExpiry:
    def test_returns_int(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        exp = demo_security.token_expiry(token)
        assert isinstance(exp, int)

    def test_expiry_roughly_correct(self, demo_key):
        token = demo_security.generate_token(3600, key=demo_key)
        exp = demo_security.token_expiry(token)
        now = int(time.time())
        # Should be approximately now + 3600 (±5 s tolerance)
        assert abs(exp - (now + 3600)) < 5

    def test_bad_token_returns_none(self):
        assert demo_security.token_expiry("garbage") is None


class TestKeyLoading:
    def test_invalid_env_key_warns(self, monkeypatch):
        monkeypatch.setenv("AETHERLING_DEMO_KEY", "not-valid-hex!!")
        with pytest.warns(UserWarning):
            import importlib
            importlib.reload(demo_security)

    def test_wrong_length_env_key_warns(self, monkeypatch):
        # 10 bytes = 20 hex chars, not 64
        monkeypatch.setenv("AETHERLING_DEMO_KEY", "deadbeef" * 2)
        with pytest.warns(UserWarning):
            import importlib
            importlib.reload(demo_security)

    def test_valid_env_key_used(self, monkeypatch):
        import secrets
        import importlib
        key = secrets.token_bytes(32)
        monkeypatch.setenv("AETHERLING_DEMO_KEY", key.hex())
        importlib.reload(demo_security)
        token = demo_security.generate_token(3600)
        # Validate with the known key
        assert demo_security.validate_token(token, key=key)


# ===========================================================================
# StubAetherling
# ===========================================================================

@pytest.fixture()
def stub_agent():
    return demo_scenarios.StubAetherling(
        dna_config={
            "soul_token": "test-stub-001",
            "guardrails": ["Never impersonate a human."],
        },
        genesis_prompt="Test agent.",
    )


class TestStubAetherling:
    def test_soul_token_set(self, stub_agent):
        assert stub_agent.soul_token == "test-stub-001"

    def test_auto_soul_token_when_missing(self):
        agent = demo_scenarios.StubAetherling()
        assert agent.soul_token  # truthy

    def test_perceive_and_act_returns_tuple(self, stub_agent):
        result = stub_agent.perceive_and_act({"message": "hello"})
        assert isinstance(result, tuple) and len(result) == 2

    def test_perceive_and_act_outcome_status(self, stub_agent):
        outcome, _ = stub_agent.perceive_and_act({"message": "hello"})
        assert outcome.get("status") == "executed"

    def test_dream_and_mutate_returns_string(self, stub_agent):
        result = stub_agent.dream_and_mutate()
        assert isinstance(result, str)

    def test_memory_grows(self, stub_agent):
        stub_agent.perceive_and_act({"message": "first"})
        assert len(stub_agent.memory._experiences) == 1


# ===========================================================================
# Individual scenarios
# ===========================================================================

class TestScenarioPerceiveAndAct:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_perceive_and_act(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "perceive_and_act"


class TestScenarioDreamAndMutate:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_dream_and_mutate(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "dream_and_mutate"


class TestScenarioConstitutionRejection:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_constitution_rejection(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "constitution_rejection"

    def test_safe_prompt_not_rejected(self, stub_agent):
        # Sanity check the constitution itself
        assert stub_agent.constitution.validate_mutation("Be more creative.")


class TestScenarioMemoryRoundTrip:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_memory_round_trip(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "memory_round_trip"


class TestScenarioSoulTokenIntegrity:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_soul_token_integrity(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "soul_token_integrity"


class TestScenarioRuntimeGuardrailAddition:
    def test_passes(self, stub_agent):
        result = demo_scenarios.scenario_runtime_guardrail_addition(stub_agent)
        assert result["passed"]
        assert result["scenario"] == "runtime_guardrail_addition"

    def test_rule_persists_after_addition(self, stub_agent):
        rule = "Do not exceed $100/day."
        stub_agent.constitution.add_user_rule(rule)
        assert rule in stub_agent.constitution.all_rules

    def test_empty_rule_raises(self, stub_agent):
        with pytest.raises(ValueError):
            stub_agent.constitution.add_user_rule("")


class TestRunAllScenarios:
    def test_all_six_run(self):
        results = demo_scenarios.run_all_scenarios()
        assert len(results) == 6

    def test_all_pass(self):
        results = demo_scenarios.run_all_scenarios()
        for r in results:
            assert r["passed"], f"Scenario {r['scenario']!r} failed: {r['detail']}"

    def test_result_structure(self):
        results = demo_scenarios.run_all_scenarios()
        for r in results:
            assert "scenario" in r
            assert "passed" in r
            assert "detail" in r


# ===========================================================================
# DemoRuntime
# ===========================================================================

@pytest.fixture()
def short_runtime(demo_key):
    """A runtime with a very short duration (2 s) and interval (1 s)."""
    token = demo_security.generate_token(10, key=demo_key)
    return DemoRuntime(
        token=token,
        key=demo_key,
        duration_seconds=2,
        interval_seconds=1,
    )


class TestDemoRuntime:
    def test_start_raises_on_invalid_token(self):
        rt = DemoRuntime(token="invalid.token", duration_seconds=60, interval_seconds=10)
        with pytest.raises(ValueError):
            rt.start()

    def test_start_raises_when_already_running(self, short_runtime):
        short_runtime.start()
        try:
            with pytest.raises(RuntimeError):
                short_runtime.start()
        finally:
            short_runtime.stop()
            short_runtime.join(timeout=3)

    def test_is_running_after_start(self, short_runtime):
        short_runtime.start()
        assert short_runtime.is_running
        short_runtime.stop()
        short_runtime.join(timeout=3)

    def test_is_not_running_after_stop(self, short_runtime):
        short_runtime.start()
        short_runtime.stop()
        short_runtime.join(timeout=3)
        assert not short_runtime.is_running

    def test_collects_results(self, demo_key):
        token = demo_security.generate_token(10, key=demo_key)
        rt = DemoRuntime(token=token, key=demo_key, duration_seconds=3, interval_seconds=1)
        rt.start()
        rt.join(timeout=5)
        assert len(rt.results) >= 1

    def test_on_scenario_callback_called(self, demo_key):
        called = []
        token = demo_security.generate_token(10, key=demo_key)
        rt = DemoRuntime(
            token=token,
            key=demo_key,
            duration_seconds=3,
            interval_seconds=1,
            on_scenario=lambda r: called.append(r),
        )
        rt.start()
        rt.join(timeout=5)
        assert len(called) >= 1

    def test_expired_token_stops_runtime(self):
        import secrets
        key = secrets.token_bytes(32)
        # Token that is valid for 1 s; runtime interval is 2 s so the token
        # will expire before the second tick.
        token = demo_security.generate_token(1, key=key)
        rt = DemoRuntime(token=token, key=key, duration_seconds=10, interval_seconds=2)
        rt.start()
        rt.join(timeout=6)
        # Runtime must have stopped on its own
        assert not rt.is_running

    def test_results_is_snapshot(self, short_runtime):
        short_runtime.start()
        short_runtime.join(timeout=3)
        r1 = short_runtime.results
        r2 = short_runtime.results
        assert r1 == r2
        assert r1 is not r2  # must be a copy each time
