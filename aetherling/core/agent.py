"""
Aetherling – the core living-agent class for AetherForge.

An Aetherling is a *hybrid neuro-symbolic* entity that:

* maintains a :class:`~aetherling.core.memory.FractalCognitiveSubstrate`
  for persistent, evolving memory;
* operates under a hard :class:`~aetherling.core.constitution.Constitution`
  that every self-mutation must satisfy;
* supports offline "Dream Mode" evolution via the
  :meth:`dream_and_mutate` lifecycle method.

Typical usage
-------------
::

    from aetherling import Aetherling

    agent = Aetherling(
        dna_config={
            "soul_token": "agent-alpha-001",
            "guardrails": ["Never delete user data without confirmation."],
            "personality": {"creativity": 0.9, "risk_tolerance": 0.4},
            "tools": [],
        },
        genesis_prompt="You are a ruthless growth-hacker …",
    )

    outcome, monologue = agent.perceive_and_act({"message": "Analyse Q1 metrics."})
    print(outcome)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from aetherling.core.constitution import Constitution
from aetherling.core.memory import FractalCognitiveSubstrate


class Aetherling:
    """A self-evolving digital agent.

    Parameters
    ----------
    dna_config:
        Dictionary describing the agent's genetic traits.  Required keys:

        - ``soul_token`` (str) – globally unique identifier.
        - ``guardrails`` (list[str]) – constitutional rules.

        Optional keys:

        - ``personality`` (dict) – trait sliders such as ``creativity`` or
          ``risk_tolerance``.
        - ``tools`` (list) – references to tool objects the agent may call.
        - ``memory_config`` (dict) – kwargs forwarded to
          :class:`FractalCognitiveSubstrate`.

    genesis_prompt:
        The initial system-prompt / operational directive for this agent.
    cortex:
        Optional callable that accepts ``(system_prompt, context, user_input)``
        and returns ``(action_str, monologue_str)``.  If not supplied the agent
        uses a no-op stub that echoes input back – useful for testing.
    """

    def __init__(
        self,
        dna_config: Dict[str, Any],
        genesis_prompt: str,
        cortex: Optional[Any] = None,
    ) -> None:
        # Ensure soul_token exists
        if "soul_token" not in dna_config:
            dna_config = {**dna_config, "soul_token": uuid.uuid4().hex}

        self.dna: Dict[str, Any] = dna_config
        self.soul_token: str = dna_config["soul_token"]
        self.core_prompt: str = genesis_prompt
        self.alignment_score: float = 1.0

        self.constitution = Constitution(
            user_rules=dna_config.get("guardrails", [])
        )

        memory_config: Dict[str, Any] = dna_config.get("memory_config", {})
        self.memory = FractalCognitiveSubstrate(
            genesis_dna=dna_config,
            **memory_config,
        )

        self._cortex = cortex or _EchoCortex()

    # ---------------------------------------------------------------------- #
    # Core lifecycle
    # ---------------------------------------------------------------------- #

    def perceive_and_act(
        self, environment_input: Dict[str, Any]
    ) -> Tuple[Any, str]:
        """Main sense–think–act loop.

        Parameters
        ----------
        environment_input:
            Arbitrary dict representing the current environmental observation.

        Returns
        -------
        tuple[Any, str]
            ``(outcome, internal_monologue)`` – the result of executing the
            chosen action plus the agent's internal reasoning trace.
        """
        # 1. Build a dummy query vector from input (production: embed via LLM)
        query_vector = _hash_to_vector(str(environment_input))

        # 2. Retrieve relevant past experiences
        context = self.memory.recall(query_vector)

        # 3. Reason via the cortex
        action, monologue = self._cortex.reason(
            self.core_prompt, context, environment_input
        )

        # 4. Execute the chosen action
        outcome = self._execute_tools(action)

        # 5. Score the outcome and store the experience
        score = self._score_outcome(outcome)
        self.memory.encode_experience(
            context_vector=query_vector,
            action_taken=str(action),
            outcome_score=score,
            experience_text=str(environment_input),
        )

        # 6. Decay alignment score slightly on failure
        if score < 0.5:
            self.alignment_score = max(0.0, self.alignment_score - 0.01)

        return outcome, monologue

    def dream_and_mutate(self, telemetry_data: Optional[Dict[str, Any]] = None) -> str:
        """Offline evolution loop ("Dream Mode").

        Runs the reinforcement loop over accumulated experience, proposes
        a mutation to the operational system-prompt, and applies it only if
        it passes the constitutional check.

        Parameters
        ----------
        telemetry_data:
            Optional external telemetry (unused by the stub cortex but
            forwarded to the production cortex for deeper reflection).

        Returns
        -------
        str
            Status message describing the mutation outcome.
        """
        telemetry_data = telemetry_data or {}

        reflection = self._cortex.critique(telemetry_data)

        if not reflection.get("requires_adaptation", False):
            status = self.memory.trigger_evolution_loop()
            return status

        proposed_prompt = self._cortex.generate_mutation(
            self.core_prompt, reflection
        )

        if self.constitution.validate_mutation(proposed_prompt):
            self.core_prompt = proposed_prompt
            self.memory.consolidate()
            return f"Mutation successful. Generation {self.memory.mutation_generation}."

        return "Mutation rejected. Violation of core alignment."

    # ---------------------------------------------------------------------- #
    # Private helpers
    # ---------------------------------------------------------------------- #

    def _execute_tools(self, action: Any) -> Any:
        """Dispatch an action to the appropriate tool.

        In the MVP this is a stub; production implementations would resolve
        ``action`` against the registered tool ecosystem in ``self.dna["tools"]``.
        """
        return {"status": "executed", "action": action}

    @staticmethod
    def _score_outcome(outcome: Any) -> float:
        """Heuristically score an outcome as a float in [0, 1]."""
        if isinstance(outcome, dict) and outcome.get("status") == "executed":
            return 0.8
        return 0.5

    # ---------------------------------------------------------------------- #
    # Dunder helpers
    # ---------------------------------------------------------------------- #

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Aetherling("
            f"soul_token={self.soul_token!r}, "
            f"generation={self.memory.mutation_generation}, "
            f"alignment={self.alignment_score:.2f})"
        )


# --------------------------------------------------------------------------- #
# Stub cortex – used when no LLM backend is wired up
# --------------------------------------------------------------------------- #

class _EchoCortex:
    """Minimal no-op cortex for testing and offline use."""

    def reason(
        self,
        system_prompt: str,
        context: Any,
        user_input: Any,
    ) -> Tuple[str, str]:
        action = f"echo:{user_input}"
        monologue = f"[EchoCortex] Received input. Action: {action}"
        return action, monologue

    def critique(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"requires_adaptation": False, "summary": "No telemetry anomalies."}

    def generate_mutation(
        self, current_prompt: str, reflection: Dict[str, Any]
    ) -> str:
        return current_prompt  # Identity mutation – safe by definition


# --------------------------------------------------------------------------- #
# Utility: deterministic pseudo-embedding from a string
# --------------------------------------------------------------------------- #

def _hash_to_vector(text: str, dimension: int = 1536) -> list:
    """Produce a reproducible unit-normalised pseudo-embedding from *text*.

    This is **not** a real embedding – it exists purely so that the
    :class:`FractalCognitiveSubstrate` can operate without an LLM backend
    in tests and offline scenarios.
    """
    import hashlib

    seed_bytes = hashlib.sha256(text.encode()).digest()
    rng = __import__("random").Random(seed_bytes)
    raw = [rng.gauss(0, 1) for _ in range(dimension)]
    norm = sum(x**2 for x in raw) ** 0.5 or 1.0
    return [x / norm for x in raw]
