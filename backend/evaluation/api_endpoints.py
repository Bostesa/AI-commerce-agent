"""Eval API endpoints"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
from pathlib import Path
from datetime import datetime
import uuid

from evaluation.evaluate_hybrid import HybridSystemEvaluator
from evaluation.report_generator import ReportGenerator

router = APIRouter()

_running_evals: Dict[str, Dict[str, Any]] = {}


class EvaluationRequest(BaseModel):
    mode: str = "all"
    catalog_path: Optional[str] = "data/catalog.csv"
    golden_queries_path: Optional[str] = "evaluation/datasets/golden_queries.json"


class EvaluationStatus(BaseModel):
    job_id: str
    status: str
    mode: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


def run_evaluation_task(job_id: str, mode: str, catalog_path: str, golden_queries_path: str):
    """Run eval in background"""
    try:
        _running_evals[job_id]["status"] = "running"
        _running_evals[job_id]["started_at"] = datetime.now().isoformat()

        # Initialize evaluator
        evaluator = HybridSystemEvaluator(
            catalog_path=catalog_path,
            golden_queries_path=golden_queries_path
        )

        # Run evaluation based on mode
        if mode == "all":
            results = evaluator.run_all_evaluations()
        elif mode == "quick":
            results = {
                "retrieval": evaluator.evaluate_retrieval(k_values=[1, 3, 5]),
                "intent_classification": evaluator.evaluate_intent_classification()
            }
            evaluator.results = results
        elif mode == "retrieval":
            results = {"retrieval": evaluator.evaluate_retrieval()}
        elif mode == "intent":
            results = {"intent_classification": evaluator.evaluate_intent_classification()}
        elif mode == "filters":
            results = {"filter_extraction": evaluator.evaluate_filter_extraction()}
        elif mode == "diversity":
            results = {"diversity": evaluator.evaluate_diversity()}
        elif mode == "performance":
            results = {"performance": evaluator.benchmark_performance()}
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Save results
        evaluator.results = results
        output_path = f"evaluation/results/{job_id}.json"
        evaluator.save_results(output_path)

        # Also update latest
        evaluator.save_results("evaluation/results/latest.json")

        # Generate HTML report
        generator = ReportGenerator(results)
        html_path = f"evaluation/results/{job_id}.html"
        generator.generate_html_report(html_path)

        _running_evals[job_id]["status"] = "completed"
        _running_evals[job_id]["completed_at"] = datetime.now().isoformat()
        _running_evals[job_id]["results_path"] = output_path
        _running_evals[job_id]["html_path"] = html_path

    except Exception as e:
        _running_evals[job_id]["status"] = "failed"
        _running_evals[job_id]["error"] = str(e)
        _running_evals[job_id]["completed_at"] = datetime.now().isoformat()


@router.post("/run", response_model=EvaluationStatus)
async def start_evaluation(request: EvaluationRequest, background_tasks: BackgroundTasks):
    """
    Start an evaluation job in the background.

    Returns job_id to track progress.
    """
    job_id = str(uuid.uuid4())[:8]

    _running_evals[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "mode": request.mode,
        "started_at": None,
        "completed_at": None,
        "error": None
    }

    # Start background task
    background_tasks.add_task(
        run_evaluation_task,
        job_id,
        request.mode,
        request.catalog_path,
        request.golden_queries_path
    )

    return EvaluationStatus(**_running_evals[job_id])


@router.get("/status/{job_id}", response_model=EvaluationStatus)
async def get_evaluation_status(job_id: str):
    """Get status of evaluation job."""
    if job_id not in _running_evals:
        raise HTTPException(status_code=404, detail="Job not found")

    return EvaluationStatus(**_running_evals[job_id])


@router.get("/results/{job_id}")
async def get_evaluation_results(job_id: str):
    """Get results of completed evaluation."""
    if job_id not in _running_evals:
        raise HTTPException(status_code=404, detail="Job not found")

    eval_data = _running_evals[job_id]

    if eval_data["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Evaluation not completed yet (status: {eval_data['status']})")

    results_path = eval_data.get("results_path")
    if not results_path or not Path(results_path).exists():
        raise HTTPException(status_code=404, detail="Results file not found")

    with open(results_path, 'r') as f:
        results = json.load(f)

    return results


@router.get("/results/latest")
async def get_latest_results():
    """Get most recent evaluation results."""
    results_path = Path("evaluation/results/latest.json")

    if not results_path.exists():
        raise HTTPException(status_code=404, detail="No evaluation results found. Run an evaluation first.")

    with open(results_path, 'r') as f:
        results = json.load(f)

    return results


@router.get("/jobs")
async def list_evaluation_jobs():
    """List all evaluation jobs."""
    return {
        "jobs": list(_running_evals.values()),
        "count": len(_running_evals)
    }


@router.get("/reports/latest")
async def get_latest_report():
    """Get latest HTML report as string (for embedding in React)."""
    report_path = Path("evaluation/results/latest.html")

    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No report found. Run an evaluation first.")

    with open(report_path, 'r') as f:
        html_content = f.read()

    return {"html": html_content}


@router.get("/summary")
async def get_evaluation_summary():
    """Get summary of latest evaluation for dashboard display."""
    results_path = Path("evaluation/results/latest.json")

    if not results_path.exists():
        raise HTTPException(status_code=404, detail="No evaluation results found")

    with open(results_path, 'r') as f:
        results = json.load(f)

    # Extract key metrics for quick display
    summary = {
        "metadata": results.get("metadata", {}),
        "key_metrics": {}
    }

    # Retrieval metrics
    retrieval = results.get("retrieval", {})
    if retrieval and "aggregated" in retrieval:
        agg = retrieval["aggregated"]
        summary["key_metrics"]["ndcg@5"] = agg.get("ndcg@5", {}).get("mean", 0)
        summary["key_metrics"]["precision@5"] = agg.get("precision@5", {}).get("mean", 0)
        summary["key_metrics"]["recall@5"] = agg.get("recall@5", {}).get("mean", 0)
        summary["key_metrics"]["mrr"] = agg.get("mrr", {}).get("mean", 0)

    # Intent accuracy
    intent = results.get("intent_classification", {})
    if intent and "accuracy" in intent:
        summary["key_metrics"]["intent_accuracy"] = intent["accuracy"]

    # Filter accuracy
    filters = results.get("filter_extraction", {})
    if filters and "overall_accuracy" in filters:
        summary["key_metrics"]["filter_accuracy"] = filters["overall_accuracy"]

    # Performance
    performance = results.get("performance", {})
    if performance:
        summary["key_metrics"]["p95_latency_ms"] = performance.get("p95_latency_ms", 0)
        summary["key_metrics"]["throughput_qps"] = performance.get("throughput_qps", 0)

    return summary


@router.get("/history")
async def get_evaluation_history():
    """Get list of all past evaluation results."""
    results_dir = Path("evaluation/results")

    if not results_dir.exists():
        return {"evaluations": []}

    # Find all timestamped result files
    result_files = sorted(results_dir.glob("eval_*.json"), reverse=True)

    evaluations = []
    for file_path in result_files[:10]:  # Last 10 evaluations
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                metadata = data.get("metadata", {})

                # Extract key metric
                ndcg = 0
                if "retrieval" in data and "aggregated" in data["retrieval"]:
                    ndcg = data["retrieval"]["aggregated"].get("ndcg@5", {}).get("mean", 0)

                evaluations.append({
                    "filename": file_path.name,
                    "timestamp": metadata.get("start_time", ""),
                    "duration_seconds": metadata.get("duration_seconds", 0),
                    "catalog_size": metadata.get("catalog_size", 0),
                    "ndcg@5": ndcg
                })
        except Exception:
            continue

    return {"evaluations": evaluations}
