"""Two-stage vector retrieval with deterministic metadata filtering and reranking."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent


def load_documents() -> list[dict[str, Any]]:
    with (BASE_DIR / "documents.csv").open(newline="", encoding="utf-8") as handle:
        documents = list(csv.DictReader(handle))
    for document in documents:
        document["year"] = int(document["year"])
    return documents


DOCUMENTS = load_documents()
EMBEDDINGS: dict[str, list[float]] = json.loads((BASE_DIR / "embeddings.json").read_text())
RERANKER_SCORES: dict[str, dict[str, float]] = json.loads(
    (BASE_DIR / "reranker_scores.json").read_text()
)


class SearchRequest(BaseModel):
    query_id: str = Field(default="", max_length=200)
    query_vector: list[float] = Field(default_factory=list, max_length=2_000)
    top_k: int = Field(default=10, ge=0, le=5_000)
    rerank_top_n: int = Field(default=3, ge=0, le=5_000)
    filter: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title="SearchTech Vector Search", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


def matches_filter(document: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Apply AND semantics across every supplied metadata condition."""
    for key, condition in filters.items():
        if key not in document:
            return False
        value = document[key]
        if isinstance(condition, dict):
            for operator, expected in condition.items():
                if operator == "gte":
                    if value < expected:
                        return False
                elif operator == "lte":
                    if value > expected:
                        return False
                elif operator == "in":
                    if not isinstance(expected, list) or value not in expected:
                        return False
                else:
                    return False
        elif value != condition:
            return False
    return True


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return float("-inf")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return float("-inf")
    return dot / (left_norm * right_norm)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/vector-search")
def vector_search(request: SearchRequest) -> dict[str, list[str]]:
    # Invalid dimensions cannot yield a meaningful cosine ranking; returning an
    # empty, valid response is safer than silently comparing partial vectors.
    if not request.query_vector or any(not math.isfinite(value) for value in request.query_vector):
        return {"matches": []}

    first_stage: list[tuple[float, str]] = []
    for document in DOCUMENTS:
        if not matches_filter(document, request.filter):
            continue
        similarity = cosine_similarity(request.query_vector, EMBEDDINGS.get(document["doc_id"], []))
        if similarity != float("-inf"):
            first_stage.append((similarity, document["doc_id"]))

    first_stage.sort(key=lambda item: (-item[0], item[1]))
    candidate_ids = [doc_id for _, doc_id in first_stage[: request.top_k]]

    scores_for_query = RERANKER_SCORES.get(request.query_id, {})
    reranked = [(float(scores_for_query.get(doc_id, 0.0)), doc_id) for doc_id in candidate_ids]
    reranked.sort(key=lambda item: (-item[0], item[1]))
    return {"matches": [doc_id for _, doc_id in reranked[: request.rerank_top_n]]}
