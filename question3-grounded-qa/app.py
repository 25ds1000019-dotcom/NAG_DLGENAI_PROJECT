"""Grounded, no-outside-knowledge QA service."""
from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

TOKEN_RE = re.compile(r"\b[a-z0-9]+\b", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = {"a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "from", "how", "in", "is", "it", "of", "on", "the", "to", "was", "what", "when", "where", "which", "who", "why", "with"}
YEAR_RE = re.compile(r"\b(?:1[5-9]\d{2}|20\d{2}|21\d{2})\b")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


class Chunk(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20_000)


class AnswerRequest(BaseModel):
    question: str = Field(default="", max_length=5_000)
    chunks: list[Chunk] = Field(default_factory=list, max_length=100)


app = FastAPI(title="SafeAnswer Grounded QA", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["POST", "OPTIONS"], allow_headers=["*"])


def words(text: str) -> list[str]:
    return [word.lower() for word in TOKEN_RE.findall(text)]


def content_words(text: str) -> set[str]:
    return {word for word in words(text) if word not in STOPWORDS}


def named_anchors(question: str) -> set[str]:
    # Preserve entity/product names, including mixed-case names such as
    # ChromaDB or LangChain.  Without this, an answer can be incorrectly
    # grounded in a different product's chunk merely because generic terms
    # (for example "database" or "Rust") overlap.
    return {
        token.lower()
        for token in TOKEN_RE.findall(question)
        if len(token) >= 2
        and token.lower() not in STOPWORDS
        and any(character.isupper() for character in token)
    }


def unknown() -> dict[str, Any]:
    return {"answer": "I don't know", "citations": [], "confidence": 0.0, "answerable": False}


def needs_numeric_answer(question: str) -> bool:
    return any(term in question.lower() for term in ("what year", "which year", "when", "how many", "how much", "number", "percent", "percentage"))


def candidate_sentences(chunks: list[Chunk]) -> list[tuple[str, str]]:
    return [(chunk.chunk_id, sentence.strip()) for chunk in chunks for sentence in SENTENCE_RE.split(chunk.text.strip()) if sentence.strip()]


def choose_answer(question: str, chunks: list[Chunk]) -> tuple[str, list[str], float] | None:
    query, anchors = content_words(question), named_anchors(question)
    requested_numbers = set(NUMBER_RE.findall(question))
    if not query:
        return None
    ranked = []
    for chunk_id, sentence in candidate_sentences(chunks):
        sentence_words = content_words(sentence)
        if anchors and not anchors <= sentence_words:
            continue
        overlap = len(query & sentence_words)
        coverage = overlap / len(query)
        precision = overlap / len(sentence_words) if sentence_words else 0.0
        ranked.append((coverage + 0.20 * precision, chunk_id, sentence, coverage, sentence_words))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    score, chunk_id, sentence, coverage, sentence_words = ranked[0]
    numeric = needs_numeric_answer(question)
    if not (query & sentence_words):
        return None
    if numeric:
        # Do not turn a conflicting premise into an answer.  For example, a
        # context that says "released in 2017" cannot support a question that
        # asks whether it was released in 2018.
        sentence_numbers = set(NUMBER_RE.findall(sentence))
        if (
            coverage < 0.25
            or not (YEAR_RE.search(sentence) or NUMBER_RE.search(sentence))
            or not requested_numbers <= sentence_numbers
        ):
            return None
    # A partial lexical match is not enough for a grounded answer: it can
    # select a chunk mentioning the entity without supporting the requested
    # attribute (for example, a country but not its capital).
    elif coverage <= 0.50:
        return None
    if question.lower().lstrip().startswith("who ") and not ({"invented", "created", "developed", "founded", "by"} & sentence_words):
        return None
    return sentence, [chunk_id], round(min(0.95, max(0.35, 0.45 + 0.50 * coverage + 0.05 * min(score, 1.0))), 2)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/answer")
@app.post("/grounded-answer")
@app.post("/")
def answer(request: AnswerRequest) -> dict[str, Any]:
    if not request.question.strip() or not request.chunks:
        return unknown()
    selected = choose_answer(request.question, request.chunks)
    if selected is None:
        return unknown()
    answer_text, citations, confidence = selected
    # Defense in depth: never emit an ID that did not appear in this request.
    supplied_ids = {chunk.chunk_id for chunk in request.chunks}
    citations = [chunk_id for chunk_id in citations if chunk_id in supplied_ids]
    if not citations:
        return unknown()
    return {"answer": answer_text, "citations": citations, "confidence": confidence, "answerable": True}
