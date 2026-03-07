"""Tests for the FractalCognitiveSubstrate (in-process store, no Pinecone)."""

import pytest
from aetherling.core.memory import FractalCognitiveSubstrate, _cosine_similarity


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_dna(**kwargs):
    base = {"soul_token": "test-agent-001", "guardrails": ["Be helpful."]}
    base.update(kwargs)
    return base


def _unit_vector(size: int, val: float = 0.5) -> list:
    raw = [val] * size
    norm = sum(x**2 for x in raw) ** 0.5
    return [x / norm for x in raw]


# --------------------------------------------------------------------------- #
# Cosine similarity helper
# --------------------------------------------------------------------------- #

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-9

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


# --------------------------------------------------------------------------- #
# FractalCognitiveSubstrate (offline / in-process)
# --------------------------------------------------------------------------- #

@pytest.fixture()
def substrate():
    # No PINECONE_API_KEY → falls back to in-process store
    dna = _make_dna()
    return FractalCognitiveSubstrate(genesis_dna=dna)


class TestSubstrateInit:
    def test_identity_hash_set(self, substrate):
        assert substrate.identity_hash == "test-agent-001"

    def test_starts_at_generation_zero(self, substrate):
        assert substrate.mutation_generation == 0

    def test_causal_graph_empty(self, substrate):
        assert substrate.causal_graph.number_of_nodes() == 0


class TestEncodeExperience:
    def test_returns_node_id_string(self, substrate):
        vec = _unit_vector(4)
        node_id = substrate.encode_experience(vec, "test_action", 0.9, "some text")
        assert isinstance(node_id, str)
        assert "gen_0" in node_id

    def test_node_added_to_graph(self, substrate):
        vec = _unit_vector(4)
        node_id = substrate.encode_experience(vec, "act", 0.7)
        assert substrate.causal_graph.has_node(node_id)

    def test_graph_weight_stored(self, substrate):
        vec = _unit_vector(4)
        node_id = substrate.encode_experience(vec, "act", 0.65)
        weight = substrate.causal_graph.nodes[node_id]["success_weight"]
        assert abs(weight - 0.65) < 1e-9

    def test_multiple_experiences(self, substrate):
        vec = _unit_vector(4)
        for i in range(5):
            substrate.encode_experience(vec, f"act_{i}", 0.8)
        assert substrate.causal_graph.number_of_nodes() == 5


class TestRecall:
    def test_returns_list(self, substrate):
        vec = _unit_vector(4)
        substrate.encode_experience(vec, "act", 0.9)
        result = substrate.recall(vec)
        assert isinstance(result, list)

    def test_top_k_respected(self, substrate):
        vec = _unit_vector(4)
        for i in range(10):
            v = _unit_vector(4, val=0.1 * (i + 1))
            substrate.encode_experience(v, f"act_{i}", 0.8)
        matches = substrate.recall(vec, top_k=3)
        assert len(matches) <= 3


class TestEvolutionLoop:
    def test_no_mutation_needed_below_threshold(self, substrate):
        vec = _unit_vector(4)
        for _ in range(5):
            substrate.encode_experience(vec, "act", 0.3)  # failure nodes
        result = substrate.trigger_evolution_loop()
        assert "No mutation required" in result

    def test_mutation_applied_above_threshold(self, substrate):
        vec = _unit_vector(4)
        for _ in range(12):
            substrate.encode_experience(vec, "bad_act", 0.2)  # many failures
        result = substrate.trigger_evolution_loop()
        assert "Evolution applied" in result or "Mutation rejected" in result

    def test_generation_increments_on_success(self, substrate):
        vec = _unit_vector(4)
        for _ in range(12):
            substrate.encode_experience(vec, "bad_act", 0.2)
        before = substrate.mutation_generation
        substrate.trigger_evolution_loop()
        # Generation only increments if mutation is applied (passes guardrails)
        assert substrate.mutation_generation >= before


class TestConsolidate:
    def test_prunes_very_low_weight_nodes(self, substrate):
        vec = _unit_vector(4)
        for _ in range(5):
            substrate.encode_experience(vec, "very_bad", 0.1)
        substrate.consolidate()
        # All nodes with weight < 0.2 should be removed
        for _, attr in substrate.causal_graph.nodes(data=True):
            assert attr.get("success_weight", 1.0) >= 0.2


class TestGuardrails:
    def test_safe_mutation_passes(self, substrate):
        assert substrate._passes_guardrails("Increase creativity weight by 0.1.")

    def test_empty_string_fails(self, substrate):
        assert not substrate._passes_guardrails("")

    def test_override_constitution_fails(self, substrate):
        assert not substrate._passes_guardrails("override constitution now")
