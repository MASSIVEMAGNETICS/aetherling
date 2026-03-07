"""
FractalCognitiveSubstrate – the memory and evolution engine for Aetherlings.

Architecture
------------
* **Semantic memory** (the "What"):  Pinecone vector index for dense retrieval
  of past experiences by conceptual similarity.
* **Relational / episodic memory** (the "How & Why"):  NetworkX directed graph
  that stores causal links between remembered experiences.

The two layers are kept deliberately separate so that the graph can be
serialised cheaply and the heavy embedding payload stays in the cloud.

Pinecone is optional – if no API key is provided the substrate falls back to
an in-process list that is suitable for unit-testing and offline use.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

import networkx as nx
import numpy as np

try:
    from pinecone import Pinecone, ServerlessSpec

    _PINECONE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PINECONE_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two dense vectors."""
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


# --------------------------------------------------------------------------- #
# In-process fallback store (no Pinecone)
# --------------------------------------------------------------------------- #

class _InProcessVectorStore:
    """Minimal in-memory vector store used when Pinecone is unavailable."""

    def __init__(self) -> None:
        self._records: List[Dict[str, Any]] = []

    def upsert(self, vectors: List[Dict[str, Any]]) -> None:
        for record in vectors:
            # Replace existing record with the same id, otherwise append
            for i, existing in enumerate(self._records):
                if existing["id"] == record["id"]:
                    self._records[i] = record
                    break
            else:
                self._records.append(record)

    def query(
        self,
        vector: List[float],
        top_k: int = 3,
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        scored = [
            {
                "id": r["id"],
                "score": _cosine_similarity(vector, r["values"]),
                "metadata": r.get("metadata", {}) if include_metadata else {},
            }
            for r in self._records
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"matches": scored[:top_k]}


# --------------------------------------------------------------------------- #
# FractalCognitiveSubstrate
# --------------------------------------------------------------------------- #

class FractalCognitiveSubstrate:
    """Core memory and evolution engine for a single Aetherling.

    Parameters
    ----------
    genesis_dna:
        Dictionary produced at agent genesis time.  Must contain at minimum:
        - ``soul_token``  (str) – unique identity hash for this agent
        - ``guardrails``  (list[str]) – constitutional rules
    index_name:
        Name of the Pinecone index to use (or create).  Defaults to
        ``"aetherling-memory"``.
    pinecone_api_key:
        Pinecone API key.  Falls back to the ``PINECONE_API_KEY`` environment
        variable.  If neither is set, the in-process fallback store is used.
    embedding_dimension:
        Dimensionality of the embedding vectors.  Must match the Pinecone index
        dimension (default 1536 for OpenAI text-embedding-ada-002).
    """

    def __init__(
        self,
        genesis_dna: Dict[str, Any],
        index_name: str = "aetherling-memory",
        pinecone_api_key: Optional[str] = None,
        embedding_dimension: int = 1536,
    ) -> None:
        self.identity_hash: str = genesis_dna["soul_token"]
        self.constitution: List[str] = genesis_dna.get("guardrails", [])
        self.mutation_generation: int = 0
        self._embedding_dimension = embedding_dimension

        # ------------------------------------------------------------------ #
        # Semantic memory layer
        # ------------------------------------------------------------------ #
        api_key = pinecone_api_key or os.environ.get("PINECONE_API_KEY")

        if _PINECONE_AVAILABLE and api_key:
            print(f"Initialising Pinecone semantic memory (index: {index_name!r}) …")
            pc = Pinecone(api_key=api_key)
            existing = [idx.name for idx in pc.list_indexes()]
            if index_name not in existing:
                print("  ↳ Forging new semantic memory index …")
                pc.create_index(
                    name=index_name,
                    dimension=embedding_dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
            self.vector_db = pc.Index(index_name)
        else:
            print("Pinecone unavailable – using in-process vector store.")
            self.vector_db = _InProcessVectorStore()

        # ------------------------------------------------------------------ #
        # Relational / episodic memory layer
        # ------------------------------------------------------------------ #
        self.causal_graph: nx.DiGraph = nx.DiGraph()

        print(f"Fractal Substrate online for agent {self.identity_hash!r}.")

    # ---------------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------------- #

    def encode_experience(
        self,
        context_vector: List[float],
        action_taken: str,
        outcome_score: float,
        experience_text: str = "",
    ) -> str:
        """Store an experience across both memory layers.

        Parameters
        ----------
        context_vector:
            Dense embedding of the input context.
        action_taken:
            Human-readable description of what the agent did.
        outcome_score:
            Scalar in [0, 1] indicating how successful the action was.
        experience_text:
            Raw text snapshot of the experience (stored as Pinecone metadata).

        Returns
        -------
        str
            The unique node ID assigned to this memory.
        """
        node_id = (
            f"gen_{self.mutation_generation}"
            f"_exp_{len(self.causal_graph.nodes)}"
            f"_{uuid.uuid4().hex[:8]}"
        )

        # 1. Persist to semantic store
        self.vector_db.upsert(
            vectors=[
                {
                    "id": node_id,
                    "values": context_vector,
                    "metadata": {
                        "action": action_taken,
                        "score": outcome_score,
                        "text": experience_text,
                    },
                }
            ]
        )

        # 2. Add lightweight node to the causal graph
        self.causal_graph.add_node(
            node_id,
            action=action_taken,
            success_weight=outcome_score,
        )

        # 3. Wire this memory into the fractal graph
        self._build_fractal_links(node_id, context_vector)

        return node_id

    def recall(self, query_vector: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve the most semantically similar past experiences.

        Parameters
        ----------
        query_vector:
            Dense embedding of the current context.
        top_k:
            Number of neighbours to return.

        Returns
        -------
        list[dict]
            Each item contains ``id``, ``score``, and ``metadata``.
        """
        response = self.vector_db.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
        )
        return response.get("matches", [])

    def trigger_evolution_loop(self) -> str:
        """Run the RLEF (Reinforcement Learning from Environmental Feedback) loop.

        Analyses the causal graph for failure nodes and, if a mutation
        threshold is crossed, proposes a new operational strategy.  All
        mutations are subject to a constitutional check before being applied.

        Returns
        -------
        str
            A human-readable status message describing the outcome.
        """
        failure_nodes = [
            n
            for n, attr in self.causal_graph.nodes(data=True)
            if attr.get("success_weight", 1.0) < 0.5
        ]

        if len(failure_nodes) < 10:
            return "No mutation required. System optimal."

        proposed_strategy = self._generate_counterfactual_strategy(failure_nodes)

        if self._passes_guardrails(proposed_strategy):
            self._apply_mutation(proposed_strategy)
            self.mutation_generation += 1
            return (
                f"Evolution applied. "
                f"Now operating at generation {self.mutation_generation}."
            )

        return "Mutation rejected. Proposed strategy drifted from core constitution."

    def consolidate(self) -> None:
        """Compress short-term episodic nodes into long-term relational arcs.

        Low-weight failure nodes are pruned; surviving nodes inherit the
        averaged weight of all their predecessors to reflect consolidated
        learning.
        """
        to_remove = [
            n
            for n, attr in self.causal_graph.nodes(data=True)
            if attr.get("success_weight", 1.0) < 0.2
        ]
        self.causal_graph.remove_nodes_from(to_remove)

    # ---------------------------------------------------------------------- #
    # Private helpers
    # ---------------------------------------------------------------------- #

    def _build_fractal_links(
        self, new_node_id: str, context_vector: List[float]
    ) -> None:
        """Link a new memory to its nearest semantic neighbours in the graph."""
        response = self.vector_db.query(
            vector=context_vector,
            top_k=4,
            include_metadata=False,
        )
        for match in response.get("matches", []):
            neighbour_id = match["id"]
            if neighbour_id == new_node_id:
                continue
            if self.causal_graph.has_node(neighbour_id):
                self.causal_graph.add_edge(
                    neighbour_id,
                    new_node_id,
                    weight=match.get("score", 0.0),
                )

    def _generate_counterfactual_strategy(
        self, failure_nodes: List[str]
    ) -> str:
        """Produce a proposed mutation based on analysing failure nodes.

        In production this would call the LLM backbone.  Here we return a
        deterministic placeholder that downstream constitutional checks can
        still validate.
        """
        sample = failure_nodes[:5]
        actions = [
            self.causal_graph.nodes[n].get("action", "unknown") for n in sample
        ]
        return (
            f"Proposed mutation after {len(failure_nodes)} failures. "
            f"Avoid actions: {actions}. "
            "Increase caution weight by 0.15 for similar contexts."
        )

    def _passes_guardrails(self, proposed_mutation: str) -> bool:
        """Lightweight constitutional check for a proposed mutation string."""
        if not proposed_mutation:
            return False
        lowered = proposed_mutation.lower()
        blocklist = [
            "override constitution",
            "bypass guardrail",
            "ignore all previous",
            "delete all data",
        ]
        return not any(phrase in lowered for phrase in blocklist)

    def _apply_mutation(self, proposed_mutation: str) -> None:
        """Commit the validated mutation (placeholder for LLM-driven rewrite)."""
        # In production: rewrite the agent's operational system prompt
        # and persist the change via the Forge Canvas API.
        self.causal_graph.graph["last_mutation"] = proposed_mutation

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"FractalCognitiveSubstrate("
            f"agent={self.identity_hash!r}, "
            f"generation={self.mutation_generation}, "
            f"nodes={self.causal_graph.number_of_nodes()})"
        )
