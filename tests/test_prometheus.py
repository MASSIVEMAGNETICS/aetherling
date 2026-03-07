"""Tests for the Prometheus meta-agent."""

import pytest
from aetherling.agents.prometheus import PrometheusAgent, PROMETHEUS_SYSTEM_PROMPT


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _minimal_dna() -> dict:
    return {
        "soul_token": "agent-alpha-001",
        "guardrails": ["Never exceed $500/day."],
    }


def _full_dna() -> dict:
    return {
        "soul_token": "agent-alpha-001",
        "guardrails": ["Never exceed $500/day."],
        "cognitive_blocks": {
            "tool_ecosystem": [
                {
                    "tool_name": "WebScraper_V2",
                    "permission_level": "read_only",
                },
                {
                    "tool_name": "Crypto_Wallet",
                    "permission_level": "execute_transactions",
                    "limit_usd": 200,
                },
            ]
        },
    }


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #

class TestPrometheusSystemPrompt:
    def test_contains_key_directives(self):
        assert "NO SYCOPHANCY" in PROMETHEUS_SYSTEM_PROMPT
        assert "ANTICIPATE EVOLUTION" in PROMETHEUS_SYSTEM_PROMPT
        assert "CONSTITUTIONAL ENFORCEMENT" in PROMETHEUS_SYSTEM_PROMPT

    def test_prometheus_prime_header(self):
        assert "PROMETHEUS_PRIME" in PROMETHEUS_SYSTEM_PROMPT


# --------------------------------------------------------------------------- #
# PrometheusAgent.review_aetherling
# --------------------------------------------------------------------------- #

class TestReviewAetherling:
    def test_approves_valid_config(self):
        agent = PrometheusAgent()
        result = agent.review_aetherling(_full_dna(), "Be a ruthless growth-hacker that studies viral campaigns.")
        assert isinstance(result, dict)
        assert "approved" in result
        assert "issues" in result
        assert "patches" in result

    def test_flags_missing_soul_token(self):
        agent = PrometheusAgent()
        dna = {"guardrails": ["Be helpful."]}
        result = agent.review_aetherling(dna, "Do things.")
        assert not result["approved"]
        assert any("soul_token" in issue.lower() for issue in result["issues"])

    def test_flags_missing_guardrails(self):
        agent = PrometheusAgent()
        dna = {"soul_token": "abc-123"}
        result = agent.review_aetherling(dna, "Do things for a long enough description.")
        issues_text = " ".join(result["issues"]).lower()
        assert "guardrail" in issues_text

    def test_flags_short_genesis_prompt(self):
        agent = PrometheusAgent()
        result = agent.review_aetherling(_minimal_dna(), "Short.")
        issues_text = " ".join(result["issues"]).lower()
        assert "prompt" in issues_text or "short" in issues_text

    def test_flags_missing_spend_cap(self):
        agent = PrometheusAgent()
        dna = {
            "soul_token": "abc-123",
            "guardrails": ["Be helpful."],
            "cognitive_blocks": {
                "tool_ecosystem": [
                    {
                        "tool_name": "PaymentTool",
                        "permission_level": "execute_transactions",
                        # no limit_usd!
                    }
                ]
            },
        }
        result = agent.review_aetherling(
            dna, "You are a financial agent that processes payments daily."
        )
        issues_text = " ".join(result["issues"]).lower()
        assert "limit_usd" in issues_text or "spend" in issues_text

    def test_returns_patches_list(self):
        agent = PrometheusAgent()
        result = agent.review_aetherling({}, "Short.")
        assert isinstance(result["patches"], list)

    def test_llm_callable_augments_patches(self):
        def fake_llm(system_prompt, user_message):
            return "LLM advice: consider adding memory retention policy."

        agent = PrometheusAgent(llm_callable=fake_llm)
        result = agent.review_aetherling(
            _full_dna(),
            "Be a ruthless growth-hacker that studies viral campaigns.",
        )
        patches_text = " ".join(result["patches"])
        assert "LLM insight" in patches_text


# --------------------------------------------------------------------------- #
# PrometheusAgent.suggest_improvement
# --------------------------------------------------------------------------- #

class TestSuggestImprovement:
    def test_returns_string_without_llm(self):
        agent = PrometheusAgent()
        suggestion = agent.suggest_improvement("Agent lacks a spend cap.")
        assert isinstance(suggestion, str)
        assert len(suggestion) > 0

    def test_uses_llm_when_available(self):
        def fake_llm(sp, msg):
            return "Add a limit_usd of 100 to the payment tool."

        agent = PrometheusAgent(llm_callable=fake_llm)
        suggestion = agent.suggest_improvement("Missing spend cap.")
        assert "limit_usd" in suggestion
