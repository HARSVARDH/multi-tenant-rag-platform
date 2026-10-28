"""Benchmark the platform's retrieval stack on a BEIR dataset.

Compares BM25-only, dense-only, hybrid (RRF), and hybrid + rerank using the
project's own VectorSearch, BM25Search, HybridSearch, and Reranker classes.
Qdrant runs in-memory, so Docker and Postgres are not needed.

Also runs a tenant-isolation check: a decoy tenant gets exact copies of
relevant documents, and no decoy may appear in the real tenant's results.

Usage (from backend/):
    .venv/bin/python scripts/run_beir_eval.py --data data/beir/scifact

Free local models (needs `pip install fastembed`):
    python scripts/run_beir_eval.py --data data/beir/scifact \
        --local-embedder BAAI/bge-small-en-v1.5 \
        --local-reranker Xenova/ms-marco-MiniLM-L-6-v2
"""

import argparse
import csv
import json
import math
import sys
import time
import uuid
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.embeddings import OpenAIEmbeddings  # noqa: E402
from app.retrieval.bm25 import BM25Search  # noqa: E402
from app.retrieval.hybrid_search import HybridSearch  # noqa: E402
from app.retrieval.reranker import Reranker  # noqa: E402
from app.retrieval.vector_search import VectorSearch  # noqa: E402

TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")
DECOY_PREFIX = "decoy-"


def load_beir(path: Path):
    corpus = {}
    with open(path / "corpus.jsonl") as f:
        for line in f:
            d = json.loads(line)
            corpus[d["_id"]] = (d.get("title", "") + " " + d["text"]).strip()
    queries = {}
    with open(path / "queries.jsonl") as f:
        for line in f:
            d = json.loads(line)
            queries[d["_id"]] = d["text"]
    qrels = {}
    with open(path / "qrels" / "test.tsv") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for qid, did, score in reader:
            if int(score) > 0:
                qrels.setdefault(qid, {})[did] = int(score)
    queries = {q: queries[q] for q in qrels if q in queries}
    return corpus, queries, qrels


class CachedEmbeddings(OpenAIEmbeddings):
    """Embeds each distinct query once, however many methods ask for it."""

    def __init__(self):
        super().__init__()
        self.cache = {}

    def get_embeddings(self, texts, batch_size=100):
        missing = [t for t in texts if t not in self.cache]
        if missing:
            for t, v in zip(missing, super().get_embeddings(missing, batch_size)):
                self.cache[t] = v
        return [self.cache[t] for t in texts]


class LocalEmbeddings:
    """Free local stand-in for OpenAIEmbeddings (fastembed / ONNX).

    get_embeddings() is what VectorSearch calls, so it embeds queries;
    embed_documents() is used only for the corpus.
    """

    def __init__(self, model: str):
        from fastembed import TextEmbedding

        self.model = model
        self._m = TextEmbedding(model)
        self.cache = {}

    def get_embeddings(self, texts, batch_size=100):
        missing = [t for t in texts if t not in self.cache]
        for t, v in zip(missing, self._m.query_embed(missing)):
            self.cache[t] = v.tolist()
        return [self.cache[t] for t in texts]

    def embed_documents(self, texts):
        return [v.tolist() for v in self._m.embed(texts, batch_size=64)]


class LocalReranker:
    """Free local cross-encoder with the same rerank() contract as Reranker."""

    def __init__(self, model: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = model
        self._m = TextCrossEncoder(model)
        self.cohere_api_key = None

    def rerank(self, query, documents, limit=5):
        scores = list(self._m.rerank(query, [d["text"] for d in documents]))
        ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
        return [dict(d, score=float(s)) for d, s in ranked[:limit]]


def embed_corpus(corpus, cache_file: Path, embedder):
    ids = list(corpus)
    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=True).item()
        if data["ids"] == ids:
            print(f"Loaded cached corpus embeddings from {cache_file}")
            return ids, data["vectors"]
    print(f"Embedding {len(ids)} documents with {embedder.model} ...")
    texts = [corpus[i] for i in ids]
    if hasattr(embedder, "embed_documents"):
        vectors = np.array(embedder.embed_documents(texts), dtype=np.float32)
    else:
        vectors = np.array(embedder.get_embeddings(texts), dtype=np.float32)
    np.save(cache_file, {"ids": ids, "vectors": vectors})
    return ids, vectors


def build_index(corpus, ids, vectors, qrels):
    client = QdrantClient(":memory:")
    client.create_collection(
        "documents", vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE)
    )
    points = [
        PointStruct(
            id=n,
            vector=vectors[n].tolist(),
            payload={"owner_id": str(TENANT_A), "document_id": did, "filename": did,
                     "chunk_index": 0, "text": corpus[did]},
        )
        for n, did in enumerate(ids)
    ]
    # Decoy tenant: exact copies of every relevant document, so a missing
    # tenant filter would surface them with identical scores.
    relevant = sorted({d for rel in qrels.values() for d in rel if d in corpus})
    pos = {did: n for n, did in enumerate(ids)}
    for k, did in enumerate(relevant):
        points.append(PointStruct(
            id=len(ids) + k,
            vector=vectors[pos[did]].tolist(),
            payload={"owner_id": str(TENANT_B), "document_id": DECOY_PREFIX + did,
                     "filename": did, "chunk_index": 0, "text": corpus[did]},
        ))
    for i in range(0, len(points), 512):
        client.upsert("documents", points[i:i + 512])
    return client, len(relevant)


def make_searchers(client, embedder):
    vs = VectorSearch.__new__(VectorSearch)
    vs.qdrant, vs.embeddings, vs.collection_name = client, embedder, "documents"
    bm = BM25Search.__new__(BM25Search)
    bm.qdrant, bm.collection_name = client, "documents"
    hy = HybridSearch.__new__(HybridSearch)
    hy.vector_search, hy.bm25_search = vs, bm
    return vs, bm, hy


def metrics(ranked, rel, k_hit=5, k_ndcg=10):
    hit = any(d in rel for d in ranked[:k_hit])
    rr = next((1.0 / (i + 1) for i, d in enumerate(ranked[:k_hit]) if d in rel), 0.0)
    dcg = sum(rel.get(d, 0) / math.log2(i + 2) for i, d in enumerate(ranked[:k_ndcg]))
    ideal = sorted(rel.values(), reverse=True)[:k_ndcg]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    recall = len({d for d in ranked[:k_ndcg] if d in rel}) / len(rel)
    return {"hit@5": hit, "mrr@5": rr, "ndcg@10": dcg / idcg if idcg else 0.0, "recall@10": recall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/beir/scifact")
    ap.add_argument("--max-queries", type=int, default=0, help="0 = all test queries")
    ap.add_argument("--rerank-pool", type=int, default=20)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--local-embedder", help="fastembed model, e.g. BAAI/bge-small-en-v1.5")
    ap.add_argument("--local-reranker", help="fastembed cross-encoder, e.g. Xenova/ms-marco-MiniLM-L-6-v2")
    args = ap.parse_args()

    data = Path(args.data)
    corpus, queries, qrels = load_beir(data)
    if args.max_queries:
        queries = dict(list(queries.items())[: args.max_queries])
    print(f"Corpus: {len(corpus)} docs | test queries: {len(queries)}")

    embedder = LocalEmbeddings(args.local_embedder) if args.local_embedder else CachedEmbeddings()
    cache_name = "corpus_embeddings_" + embedder.model.replace("/", "_") + ".npy"
    ids, vectors = embed_corpus(corpus, data / cache_name, embedder)
    client, n_decoys = build_index(corpus, ids, vectors, qrels)
    vs, bm, hy = make_searchers(client, embedder)

    if args.local_reranker:
        reranker = LocalReranker(args.local_reranker)
        reranker_name = args.local_reranker
    else:
        reranker = Reranker()
        reranker_name = "cohere" if reranker.cohere_api_key else "openai-llm"
    used = {"cohere": 0, "openai": 0, "local": 0, "none": 0}

    methods = {
        "bm25": lambda q: bm.search(q, TENANT_A, limit=10),
        "dense": lambda q: vs.search(q, TENANT_A, limit=10),
        "hybrid_rrf": lambda q: hy.search(q, TENANT_A, limit=10),
    }
    if not args.no_rerank:
        def rerank(q):
            pool = hy.search(q, TENANT_A, limit=args.rerank_pool)
            out = reranker.rerank(q, pool, limit=10)
            if args.local_reranker:
                used["local"] += 1
            elif out == pool[:10]:
                used["none"] += 1
            elif reranker.cohere_api_key:
                used["cohere"] += 1
            else:
                used["openai"] += 1
            return out
        methods[f"hybrid_rrf+rerank({reranker_name})"] = rerank

    results, leaks, latencies = {}, 0, {}
    for name, fn in methods.items():
        totals, times = {}, []
        for n, (qid, text) in enumerate(queries.items(), 1):
            t0 = time.perf_counter()
            hits = fn(text)
            times.append(time.perf_counter() - t0)
            ranked = [str(h["document_id"]) for h in hits]
            leaks += sum(r.startswith(DECOY_PREFIX) for r in ranked)
            for m, v in metrics(ranked, qrels[qid]).items():
                totals[m] = totals.get(m, 0.0) + v
            if n % 50 == 0:
                print(f"  {name}: {n}/{len(queries)}")
        results[name] = {m: round(v / len(queries), 4) for m, v in totals.items()}
        latencies[name] = round(1000 * float(np.median(times)), 1)
        print(f"{name}: {results[name]} | median latency {latencies[name]} ms")

    report = {
        "dataset": data.name,
        "corpus_size": len(corpus),
        "num_queries": len(queries),
        "embedding_model": embedder.model,
        "reranker": None if args.no_rerank else reranker_name,
        "results": results,
        "median_latency_ms": latencies,
        "rerank_calls": used,
        "tenant_isolation": {
            "decoy_docs_in_other_tenant": n_decoys,
            "queries_checked": len(queries) * len(methods),
            "leaked_results": leaks,
        },
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    out = Path("eval_results") / f"beir_{data.name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
