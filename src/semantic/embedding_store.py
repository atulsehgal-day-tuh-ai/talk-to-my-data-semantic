# src/semantic/embedding_store.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any

import numpy as np
from openai import OpenAI

from .semantic_model import SemanticModel


EmbeddingType = Literal["measure", "dimension"]


@dataclass
class EmbeddingItem:
    """
    One semantic concept represented in the embedding index.
    """
    type: EmbeddingType  # "measure" or "dimension"
    name: str            # semantic name (e.g. "revenue", "region")
    table: Optional[str] # physical table (for dimensions)
    column: Optional[str]
    text: str            # full text used to compute embedding


class EmbeddingIndex:
    """
    In-memory embedding index with simple cosine similarity search.
    """

    def __init__(self, items: List[EmbeddingItem], vectors: np.ndarray):
        assert len(items) == vectors.shape[0]
        self.items = items

        # Normalize vectors for fast cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8
        self.vectors = vectors / norms

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "EmbeddingIndex":
        items_data = payload["items"]
        vectors = np.array(payload["vectors"], dtype="float32")

        items = [
            EmbeddingItem(
                type=item["type"],
                name=item["name"],
                table=item.get("table"),
                column=item.get("column"),
                text=item["text"],
            )
            for item in items_data
        ]
        return cls(items, vectors)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [
                {
                    "type": it.type,
                    "name": it.name,
                    "table": it.table,
                    "column": it.column,
                    "text": it.text,
                }
                for it in self.items
            ],
            "vectors": self.vectors.tolist(),
        }

    # ------------- Search -------------

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        type_filter: Optional[EmbeddingType] = None,
    ) -> List[tuple[EmbeddingItem, float]]:
        """
        Return top_k (item, score) pairs by cosine similarity.
        Optionally restrict to "measure" or "dimension".
        """
        q = query_vector.astype("float32")
        q = q / (np.linalg.norm(q) + 1e-8)

        sims = self.vectors @ q  # cosine, because everything is normalized

        # Optional filter by type
        indices = range(len(self.items))
        if type_filter:
            indices = [
                i for i in indices if self.items[i].type == type_filter
            ]

        scored = [(i, float(sims[i])) for i in indices]
        scored.sort(key=lambda x: x[1], reverse=True)

        top = scored[:top_k]
        return [(self.items[i], score) for (i, score) in top]
    
    
    def search_dimension(self, query_vec, top_k=5):
        """Return best-matching dimensions."""
        return self.search(query_vec, top_k=top_k, type_filter="dimension")

    def search_measure(self, query_vec, top_k=5):
        """Return best-matching measures."""
        return self.search(query_vec, top_k=top_k, type_filter="measure")


# =====================================================================
# Helpers to BUILD an EmbeddingIndex from a SemanticModel
# =====================================================================

def _build_items_from_model(model: SemanticModel) -> List[EmbeddingItem]:
    items: List[EmbeddingItem] = []

    # Measures
    for m in model.measures.values():
        parts = [
            f"measure name: {m.name}",
            f"description: {m.description or ''}",
        ]
        if m.synonyms:
            parts.append("synonyms: " + ", ".join(m.synonyms))

        text = " | ".join(parts)
        items.append(
            EmbeddingItem(
                type="measure",
                name=m.name,
                table=m.table,
                column=None,
                text=text,
            )
        )

    # Dimensions
    for d in model.dimensions.values():
        parts = [
            f"dimension name: {d.name}",
            f"table: {d.table}",
            f"column: {d.column}",
            f"description: {d.description or ''}",
        ]
        if d.synonyms:
            parts.append("synonyms: " + ", ".join(d.synonyms))

        text = " | ".join(parts)
        items.append(
            EmbeddingItem(
                type="dimension",
                name=d.name,
                table=d.table,
                column=d.column,
                text=text,
            )
        )

    return items


def _embed_texts(texts: List[str], embedding_model: str) -> np.ndarray:
    client = OpenAI()
    resp = client.embeddings.create(
        model=embedding_model,
        input=texts,
    )
    vectors = [d.embedding for d in resp.data]
    return np.array(vectors, dtype="float32")



def build_index_from_model(model: SemanticModel, embedding_model: str) -> EmbeddingIndex:
    """
    Build an EmbeddingIndex from the current semantic model.
    Run this offline / in a notebook and persist the result.
    """
    items = _build_items_from_model(model)
    texts = [it.text for it in items]
    vectors = _embed_texts(texts, embedding_model=embedding_model)
    return EmbeddingIndex(items, vectors)



