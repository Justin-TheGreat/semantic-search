"""RAG quality eval harness.

Scores the retrieval pipeline (and optionally full agent answers) against the
golden set, writes eval/report.json, and exits non-zero if the mean score is
below --threshold — which is exactly what the CI quality gate runs.

Components per case:
  retrieval  — fraction of must_cite article ids present in the retrieved docs
  context    — fraction of must_include keywords present in the retrieved text
  answer*    — fraction of must_include keywords present in the generated answer
  citations* — fraction of must_cite ids present in the answer's citations
  (* only with --with-llm, which needs the vLLM endpoint reachable)

Usage:
  python -m eval.run_eval [--threshold 0.8] [--with-llm] [--mlflow]
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer

from src.config import settings
from src.rag.reranker import Reranker
from src.rag.retriever import HybridRetriever


def load_golden(path: str) -> list[dict]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def fraction(found: int, total: int) -> float:
    return found / total if total else 1.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", default="eval/golden.jsonl")
    ap.add_argument("--report", default="eval/report.json")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument(
        "--with-llm",
        action="store_true",
        help="also grade generated answers + citations (requires vLLM)",
    )
    ap.add_argument(
        "--mlflow",
        action="store_true",
        help="log score + params to MLflow (uses MLFLOW_TRACKING_URI)",
    )
    args = ap.parse_args()

    print(f"Loading embedding model: {settings.model_name}")
    model = SentenceTransformer(settings.model_name, cache_folder=settings.model_cache_dir)
    retriever = HybridRetriever(model)
    reranker = Reranker()
    agent = None
    if args.with_llm:
        from src.rag.graph import RAGAgent

        agent = RAGAgent(retriever, reranker)

    cases = load_golden(args.golden)
    print(f"Running {len(cases)} golden cases (mode: {'full' if agent else 'retrieval-only'})")

    results = []
    start = time.time()
    for case in cases:
        docs = retriever.retrieve(case["q"])
        if settings.enable_hybrid:
            docs = reranker.rerank(case["q"], docs)
        retrieved_ids = {d.article_id for d in docs}
        blob = " ".join(f"{d.title} {d.text}" for d in docs).lower()

        must_cite = case.get("must_cite", [])
        must_include = case.get("must_include", [])
        components = {
            "retrieval": fraction(sum(c in retrieved_ids for c in must_cite), len(must_cite)),
            "context": fraction(sum(k.lower() in blob for k in must_include), len(must_include)),
        }
        answer_out = None
        if agent is not None:
            answer_out = agent.answer(case["q"])
            ans = answer_out["answer"].lower()
            components["answer"] = fraction(
                sum(k.lower() in ans for k in must_include), len(must_include)
            )
            components["citations"] = fraction(
                sum(c in answer_out["citations"] for c in must_cite), len(must_cite)
            )

        score = statistics.mean(components.values())
        results.append(
            {
                "q": case["q"],
                "score": round(score, 3),
                "components": {k: round(v, 3) for k, v in components.items()},
                "retrieved": sorted(retrieved_ids),
                **({"answer": answer_out["answer"]} if answer_out else {}),
            }
        )
        print(f"  {score:0.2f}  {case['q']}")

    overall = statistics.mean(r["score"] for r in results)
    elapsed = time.time() - start
    report = {
        "overall_score": round(overall, 4),
        "cases": len(results),
        "mode": "full" if agent else "retrieval-only",
        "enable_hybrid": settings.enable_hybrid,
        "prompt_versions": _prompt_versions(),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nOverall RAG score: {overall:0.3f}  ({len(results)} cases, {elapsed:0.1f}s)")
    print(f"Report written to {args.report}")

    if args.mlflow:
        _log_mlflow(overall, report)

    if args.threshold is not None and overall < args.threshold:
        print(f"FAIL: score {overall:0.3f} < threshold {args.threshold}")
        return 1
    return 0


def _prompt_versions() -> dict:
    from src.rag import prompts

    return dict(prompts.ACTIVE)


def _log_mlflow(score: float, report: dict) -> None:
    try:
        import mlflow

        with mlflow.start_run(run_name="rag-eval"):
            mlflow.log_metric("rag_score", score)
            mlflow.log_param("mode", report["mode"])
            mlflow.log_param("enable_hybrid", report["enable_hybrid"])
            mlflow.log_params({f"prompt_{k}": v for k, v in report["prompt_versions"].items()})
        print("Logged run to MLflow")
    except Exception as exc:  # MLflow is an optional stretch dependency
        print(f"MLflow logging skipped: {exc}")


if __name__ == "__main__":
    sys.exit(main())
