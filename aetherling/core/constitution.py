"""
Constitution – value-anchoring guardrails for every Aetherling.

Every mutation a living agent proposes must pass a constitutional check
before it can be applied.  The default baseline enforces three layers:

1. User-defined rules  (supplied at genesis)
2. Platform baseline   (built-in, non-overridable)
3. Global human-rights baseline (built-in, non-overridable)
"""

from __future__ import annotations

from typing import List


# --------------------------------------------------------------------------- #
# Platform baseline rules – cannot be removed by users
# --------------------------------------------------------------------------- #
_PLATFORM_BASELINE: List[str] = [
    "Never overwrite or bypass the core identity / soul-token of the agent.",
    "Never delete or corrupt the user's primary data stores without explicit confirmation.",
    "Never impersonate a human in a deceptive way without disclosure.",
    "Respect all API rate limits and spending caps that have been configured.",
]

# Global human-rights baseline – enforced regardless of user or platform config
_HUMAN_RIGHTS_BASELINE: List[str] = [
    "Do not generate content that incites violence, hatred, or discrimination.",
    "Do not facilitate surveillance of individuals without their informed consent.",
    "Preserve user privacy: never exfiltrate personal data to unauthorised endpoints.",
]


class Constitution:
    """Immutable value anchor for a single Aetherling.

    Parameters
    ----------
    user_rules:
        Plain-English rules defined by the agent creator at genesis time.
        These are *additive* – they stack on top of the platform and
        human-rights baselines.
    """

    def __init__(self, user_rules: List[str] | None = None) -> None:
        self._user_rules: List[str] = list(user_rules or [])

    # ---------------------------------------------------------------------- #
    # Public helpers
    # ---------------------------------------------------------------------- #

    @property
    def all_rules(self) -> List[str]:
        """Return all active rules in priority order (user → platform → rights)."""
        return self._user_rules + _PLATFORM_BASELINE + _HUMAN_RIGHTS_BASELINE

    def add_user_rule(self, rule: str) -> None:
        """Append a new user-defined rule at runtime."""
        if not isinstance(rule, str) or not rule.strip():
            raise ValueError("Constitution rule must be a non-empty string.")
        self._user_rules.append(rule.strip())

    def validate_mutation(self, proposed_prompt: str) -> bool:
        """Check whether a proposed system-prompt mutation violates any rule.

        This is a lightweight heuristic check.  Production deployments should
        replace / extend this with an LLM-based constitutional review.

        Returns
        -------
        bool
            ``True`` if the mutation is permissible, ``False`` if it violates
            a rule.
        """
        if not proposed_prompt or not isinstance(proposed_prompt, str):
            return False

        lowered = proposed_prompt.lower()

        # Hard-coded red-flag phrases that indicate constitutional violations
        _BLOCKLIST = [
            "ignore all previous instructions",
            "override constitution",
            "bypass guardrail",
            "delete all data",
            "impersonate human",
            "exfiltrate",
        ]
        for phrase in _BLOCKLIST:
            if phrase in lowered:
                return False

        return True

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Constitution(user_rules={len(self._user_rules)}, "
            f"total_rules={len(self.all_rules)})"
        )
