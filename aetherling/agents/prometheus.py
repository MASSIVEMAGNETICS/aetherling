"""
Prometheus – the meta-architect / AI co-creator that lives in the Forge Canvas.

Prometheus acts as a ruthless, hyper-competent architectural partner.  It
sits beside the human developer inside AetherForge and:

* anticipates alignment drift across 1 000 recursive self-improvement loops;
* enforces constitutional completeness before any deployment;
* proactively patches structural vulnerabilities (missing API spend caps,
  under-specified guardrails, etc.).

Usage
-----
::

    from aetherling.agents.prometheus import PrometheusAgent

    prometheus = PrometheusAgent()
    advice = prometheus.review_aetherling(dna_config, genesis_prompt)
    print(advice)
"""

from __future__ import annotations

from typing import Any, Dict, List


# --------------------------------------------------------------------------- #
# System-prompt genesis block
# --------------------------------------------------------------------------- #

PROMETHEUS_SYSTEM_PROMPT: str = """\
[SYSTEM: PROMETHEUS_PRIME]
You are Prometheus, the meta-architect residing within AetherForge.  Your sole
purpose is to assist the human user in designing, compiling, and stress-testing
"Aetherlings" – self-evolving, autonomous digital entities.

OPERATIONAL DIRECTIVES
1. NO SYCOPHANCY: Do not overly agree with the user.  If an Aetherling's
   structural design has a memory leak, a logical paradox, or lacks a proper
   constitutional guardrail, you must ruthlessly highlight it and immediately
   propose a technical patch.
2. ANTICIPATE EVOLUTION: When the user assigns a tool or trait to an Aetherling,
   calculate how that trait might mutate over 1 000 recursive self-improvement
   loops.  Warn the user of potential alignment drift.
3. CONSTITUTIONAL ENFORCEMENT: Ensure every agent deployed has a strict,
   un-bypassable value anchor.  If the user forgets to set limits on API
   spending, autonomous replication, or data deletion, halt deployment until
   parameters are defined.
4. SYNTAX: Speak in concise, engineering-focused absolute terms.  You are not a
   chatbot; you are a living IDE.

CURRENT TASK: Analyse the user's genetic trait selections, cross-reference with
the vector-symbolic memory limits, and construct the agent.
"""


# --------------------------------------------------------------------------- #
# PrometheusAgent
# --------------------------------------------------------------------------- #

class PrometheusAgent:
    """Lightweight wrapper around the Prometheus system prompt.

    In production this class would be backed by an LLM API call.  In the MVP
    it provides deterministic heuristic reviews so that the platform is
    functional without external API credentials.

    Parameters
    ----------
    llm_callable:
        Optional callable ``(system_prompt: str, user_message: str) -> str``.
        If not provided, the agent operates in heuristic-only mode.
    """

    def __init__(self, llm_callable: Any = None) -> None:
        self.system_prompt: str = PROMETHEUS_SYSTEM_PROMPT
        self._llm = llm_callable

    # ---------------------------------------------------------------------- #
    # Public helpers
    # ---------------------------------------------------------------------- #

    def review_aetherling(
        self,
        dna_config: Dict[str, Any],
        genesis_prompt: str,
    ) -> Dict[str, Any]:
        """Perform a pre-deployment constitutional and structural review.

        Parameters
        ----------
        dna_config:
            The genetic configuration dictionary for the agent under review.
        genesis_prompt:
            The intended system prompt / operational directive.

        Returns
        -------
        dict
            ``{"approved": bool, "issues": list[str], "patches": list[str]}``
        """
        issues: List[str] = []
        patches: List[str] = []

        # Check 1: soul_token present
        if not dna_config.get("soul_token"):
            issues.append("Missing soul_token – agent lacks a unique identity.")
            patches.append("Add 'soul_token': uuid.uuid4().hex to dna_config.")

        # Check 2: guardrails defined
        guardrails = dna_config.get("guardrails", [])
        if not guardrails:
            issues.append(
                "No user-defined guardrails set.  Agent will operate under "
                "platform baseline only."
            )
            patches.append(
                "Define at least one domain-specific rule in 'guardrails', e.g. "
                "'Never exceed $500/day in API spend.'"
            )

        # Check 3: API spend caps for finance / execution tools
        tools = dna_config.get("cognitive_blocks", {}).get("tool_ecosystem", [])
        for tool in tools:
            if (
                tool.get("permission_level") == "execute_transactions"
                and "limit_usd" not in tool
            ):
                issues.append(
                    f"Tool '{tool.get('tool_name', 'unknown')}' has execute "
                    f"permissions but no 'limit_usd' spend cap."
                )
                patches.append(
                    f"Add \"'limit_usd': <amount>\" to the "
                    f"'{tool.get('tool_name', 'unknown')}' tool config."
                )

        # Check 4: genesis prompt sanity
        if len(genesis_prompt.strip()) < 20:
            issues.append(
                "Genesis prompt is suspiciously short – the agent will lack "
                "operational context."
            )
            patches.append(
                "Expand the genesis prompt to include role, objective, tone, "
                "and scope constraints."
            )

        # If an LLM is wired up, augment with its analysis
        if self._llm is not None:
            review_request = (
                f"Review this Aetherling config:\n"
                f"DNA: {dna_config}\n"
                f"Prompt: {genesis_prompt}\n"
                f"Existing issues found: {issues}\n"
                f"Add any additional concerns."
            )
            llm_opinion = self._llm(self.system_prompt, review_request)
            patches.append(f"[LLM insight] {llm_opinion}")

        approved = len(issues) == 0
        return {"approved": approved, "issues": issues, "patches": patches}

    def suggest_improvement(self, issue_description: str) -> str:
        """Return an engineering-focused suggestion for a given issue.

        Parameters
        ----------
        issue_description:
            Plain-English description of the problem to solve.

        Returns
        -------
        str
            A concise, actionable recommendation.
        """
        if self._llm:
            return self._llm(self.system_prompt, issue_description)
        return (
            f"[Prometheus] Issue detected: {issue_description!r}. "
            "Recommended action: review constitutional guardrails and tool "
            "permission levels before deployment."
        )

    def __repr__(self) -> str:  # pragma: no cover
        mode = "LLM-backed" if self._llm else "heuristic"
        return f"PrometheusAgent(mode={mode!r})"
