import json
import os
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[2]


# ---------- Embedders: turn text into numbers ----------

class TfidfEmbedder:
    """Laptop version. Matches shared words. Needs no key and no GPU."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), sublinear_tf=True
        )

    def fit_transform(self, texts):
        return self.vectorizer.fit_transform(texts)

    def transform(self, texts):
        return self.vectorizer.transform(texts)


class ApiEmbedder:
    """Real version for later. Calls the embedding model on the AMD endpoint.
    Needs EMBED_BASE_URL, EMBED_API_KEY and EMBED_MODEL in .env."""

    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(
            base_url=os.getenv("EMBED_BASE_URL"),
            api_key=os.getenv("EMBED_API_KEY", "none"),
        )
        self.model = os.getenv("EMBED_MODEL")

    def transform(self, texts):
        vectors = []
        for start in range(0, len(texts), 64):  # send 64 texts at a time
            batch = texts[start : start + 64]
            reply = self.client.embeddings.create(model=self.model, input=batch)
            vectors.extend(item.embedding for item in reply.data)
        matrix = np.array(vectors, dtype="float32")
        # make each vector length 1, so a dot product equals cosine similarity
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

    def fit_transform(self, texts):
        return self.transform(texts)


# ---------- The index: find the most similar items ----------

class Index:
    def __init__(self, items, text_of, embedder=None):
        self.items = items
        self.embedder = embedder or TfidfEmbedder()
        self.matrix = self.embedder.fit_transform([text_of(i) for i in items])

    def search(self, query, k=5, exclude_id=None, keep=None):
        """Return the k best matches as [{"item": ..., "score": 0.83}, ...]."""
        scores = self.matrix @ self.embedder.transform([query]).T
        if hasattr(scores, "toarray"):  # TF-IDF gives a sparse table
            scores = scores.toarray()
        scores = np.asarray(scores).ravel()

        results = []
        for position in np.argsort(-scores):  # best score first
            if scores[position] <= 0:
                break
            item = self.items[position]
            if exclude_id and item.get("id") == exclude_id:
                continue
            if keep and not keep(item):
                continue
            results.append({"item": item, "score": round(float(scores[position]), 2)})
            if len(results) == k:
                break
        return results


# ---------- Cards ----------

def card_text(card):
    """The text we compare for one JobCard."""
    parts = [
        card.get("component"),
        card.get("symptom"),
        (card.get("failure_mode") or "").replace("_", " "),
        card.get("action_taken"),
        (card.get("raw_text") or "")[:1000],
    ]
    return " ".join(p for p in parts if p)


_card_index = None


def get_card_index(cards):
    """Build the card index once, then reuse it."""
    global _card_index
    if _card_index is None:
        _card_index = Index(cards, card_text)
    return _card_index


def similar_cards(cards, fault_text, k=5, aircraft_type=None):
    """Past cards that look like this fault. The /api/assist step will call this."""
    keep = None
    if aircraft_type:
        keep = lambda c: c.get("aircraft_type") == aircraft_type
    found = get_card_index(cards).search(fault_text, k=k, keep=keep)
    return [{"card": r["item"], "score": r["score"]} for r in found]


# ---------- AC 43.13 procedure chunks ----------

# The text of each chunk may be stored under different names. Adjust if needed.
TEXT_KEYS = ("text", "snippet", "content")


def procedure_text(chunk):
    for key in TEXT_KEYS:
        if chunk.get(key):
            return str(chunk[key])
    # fallback: join every text value in the chunk
    return " ".join(v for v in chunk.values() if isinstance(v, str))


_procedure_index = None


def get_procedure_index():
    global _procedure_index
    if _procedure_index is None:
        path = ROOT / "data" / "procedures" / "ac_43-13-1b.jsonl"
        with open(path, encoding="utf-8") as f:
            chunks = [json.loads(line) for line in f if line.strip()]
        _procedure_index = Index(chunks, procedure_text)
    return _procedure_index


def similar_procedures(fault_text, k=3):
    found = get_procedure_index().search(fault_text, k=k)
    return [{"chunk": r["item"], "score": r["score"]} for r in found]