# Multi-Tenant RAG Platform

A retrieval-augmented generation backend with hybrid search, reranking, source citations, and per-tenant data isolation, plus Terraform for AWS.

## Features
- **Ingestion:** PDF, DOCX, Markdown, and TXT, with recursive chunking and Markdown header context added to each chunk.
- **Hybrid retrieval:** Qdrant dense search plus BM25, fused with Reciprocal Rank Fusion (k = 60).
- **Reranking:** cross-encoder stage (Cohere, falling back to an OpenAI LLM reranker).
- **Citations:** maps model `[doc-index]` references back to the exact source passages.
- **Tenant isolation:** every query is filtered by `owner_id` at the Qdrant payload level.
- **Evaluation:** Hit Rate / MRR for retrieval and LLM-as-a-judge faithfulness / relevance (`app/retrieval/evaluation.py`), plus a BEIR benchmark script.
- **Infrastructure:** FastAPI, PostgreSQL, Redis, and Qdrant via Docker Compose; Terraform for AWS (VPC, ALB, ECS, ECR, RDS, EFS, ElastiCache).

## Benchmark: BEIR SciFact
5,183 scientific abstracts and 300 labeled test queries. Run with local `BAAI/bge-small-en-v1.5` embeddings and an `ms-marco-MiniLM-L-6-v2` cross-encoder over the top 20 hybrid results.

| Method | Hit@5 | MRR@5 | nDCG@10 | Recall@10 | Median latency |
|---|---|---|---|---|---|
| BM25 | 0.757 | 0.613 | 0.652 | 0.774 | 1,924 ms |
| Dense | 0.787 | 0.675 | 0.720 | 0.845 | 43 ms |
| Hybrid (RRF) | 0.787 | 0.668 | 0.720 | 0.864 | 2,027 ms |
| Hybrid + rerank | 0.787 | 0.662 | 0.708 | 0.853 | 3,646 ms |

**Tenant isolation:** a second tenant was seeded with exact duplicates of all 283 relevant documents. Across 1,200 searches, 0 decoys were returned.

**Findings**
- Hybrid search matches dense on ranking quality and adds about 2 points of Recall@10.
- The MS MARCO reranker slightly *hurt* ranking on scientific text, which points to a domain mismatch. A domain-appropriate reranker is the next experiment.
- BM25 dominates latency: it rebuilds its index from the tenant's full corpus on every query. Caching the index per tenant is the next optimization.

Reproduce it (full results are written to `backend/eval_results/`):
```bash
cd backend
pip install fastembed
python scripts/run_beir_eval.py --data data/beir/scifact \
  --local-embedder BAAI/bge-small-en-v1.5 \
  --local-reranker Xenova/ms-marco-MiniLM-L-6-v2
```
The dataset goes in `backend/data/beir/scifact/` (`corpus.jsonl`, `queries.jsonl`, `qrels/test.tsv`) from [BEIR](https://github.com/beir-cellar/beir).

## Running locally
```bash
cp backend/.env.example backend/.env   # add your OPENAI_API_KEY
docker compose up --build
```
