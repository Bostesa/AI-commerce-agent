"""
Eval script for checking retrieval quality, intent accuracy, filters, diversity, and performance.

Usage: python -m evaluation.evaluate_hybrid --mode quick --report html
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.router import classify_intent, extract_filters_llm_or_rules, extract_filters_rules
from agent.tools import CatalogIndex, apply_filters
from agent.models import Product, FilterSpec
from evaluation.metrics import (
    calculate_all_metrics,
    aggregate_metrics,
    confusion_matrix_metrics,
    diversity_at_k,
    category_coverage
)


class HybridSystemEvaluator:
    def __init__(self, catalog_path: str = "data/catalog.csv",
                 golden_queries_path: str = "evaluation/datasets/golden_queries.json"):
        print(f"[Evaluator] Loading catalog from {catalog_path}")
        self.index = CatalogIndex(catalog_path)
        self.catalog_df = self.index.df

        print(f"[Evaluator] Loading golden queries from {golden_queries_path}")
        with open(golden_queries_path, 'r') as f:
            self.golden_data = json.load(f)

        self.results = {}
        self.start_time = None
        self.end_time = None

    def evaluate_retrieval(self, k_values: List[int] = [1, 3, 5, 8]) -> Dict[str, Any]:
        """
        Evaluate text-based retrieval quality using golden query set.

        Args:
            k_values: List of K values for metrics@K

        Returns:
            Dict with aggregated retrieval metrics
        """
        print("\n" + "=" * 60)
        print("EVALUATING TEXT RETRIEVAL QUALITY")
        print("=" * 60)

        queries = self.golden_data.get("text_recommend", [])
        all_metrics = []
        per_query_results = []

        for query_data in queries:
            query_id = query_data["query_id"]
            query_text = query_data["query"]
            relevant = set(query_data["relevant_ids"])
            expected_category = query_data.get("expected_filters", {}).get("category")

            print(f"\n[{query_id}] Query: '{query_text}'")
            print(f"  Expected relevant: {relevant}")

            # Simulate search
            try:
                # Extract filters
                filters = extract_filters_rules(query_text)
                print(f"  Extracted filters: {filters.model_dump()}")

                # Search
                start = time.time()
                scored = self.index.search_by_text(query_text, top_k=50, filters=filters)
                latency = time.time() - start

                # Get top 8 results
                retrieved_ids = [self.catalog_df.iloc[i]["id"] for i, _ in scored[:8]]
                print(f"  Retrieved: {retrieved_ids}")

                # Calculate metrics
                metrics = calculate_all_metrics(
                    relevant=relevant,
                    retrieved=retrieved_ids,
                    catalog_df=self.catalog_df,
                    k_values=k_values,
                    expected_category=expected_category
                )
                metrics["latency_ms"] = latency * 1000

                all_metrics.append(metrics)
                per_query_results.append({
                    "query_id": query_id,
                    "query": query_text,
                    "relevant": list(relevant),
                    "retrieved": retrieved_ids,
                    "metrics": metrics
                })

                # Print key metrics
                print(f"  Metrics: P@1={metrics['precision@1']:.3f}, "
                      f"R@5={metrics['recall@5']:.3f}, "
                      f"NDCG@5={metrics['ndcg@5']:.3f}, "
                      f"MRR={metrics['mrr']:.3f}")

            except Exception as e:
                print(f"  ERROR: {e}")
                continue

        # Aggregate across all queries
        aggregated = aggregate_metrics(all_metrics)

        print("\n" + "-" * 60)
        print("AGGREGATED RETRIEVAL METRICS")
        print("-" * 60)
        for metric_name in sorted(aggregated.keys()):
            stats = aggregated[metric_name]
            print(f"{metric_name:20s}: mean={stats['mean']:.4f}, "
                  f"std={stats['std']:.4f}, "
                  f"min={stats['min']:.4f}, "
                  f"max={stats['max']:.4f}")

        return {
            "aggregated": aggregated,
            "per_query": per_query_results,
            "num_queries": len(queries),
            "num_evaluated": len(all_metrics)
        }

    def evaluate_intent_classification(self) -> Dict[str, Any]:
        """
        Evaluate intent classification accuracy.

        Returns:
            Dict with accuracy and confusion matrix
        """
        print("\n" + "=" * 60)
        print("EVALUATING INTENT CLASSIFICATION")
        print("=" * 60)

        test_cases = self.golden_data.get("intent_classification", [])
        y_true = []
        y_pred = []

        for case in test_cases:
            query_id = case["query_id"]
            query = case["query"]
            has_image = case["has_image"]
            expected = case["expected_intent"]

            predicted = classify_intent(query, has_image=has_image)

            y_true.append(expected)
            y_pred.append(predicted)

            status = "✓" if predicted == expected else "✗"
            print(f"[{query_id}] {status} Query: '{query}' | Image: {has_image}")
            print(f"          Expected: {expected}, Predicted: {predicted}")

        # Calculate confusion matrix and accuracy
        labels = ["TEXT_RECOMMEND", "IMAGE_SEARCH", "IMAGE_AND_TEXT", "SMALLTALK"]
        confusion_metrics = confusion_matrix_metrics(y_true, y_pred, labels)

        print("\n" + "-" * 60)
        print(f"INTENT CLASSIFICATION ACCURACY: {confusion_metrics['accuracy']:.4f}")
        print("-" * 60)
        print("\nPer-class metrics:")
        for label, stats in confusion_metrics["per_class"].items():
            print(f"  {label:20s}: P={stats['precision']:.3f}, "
                  f"R={stats['recall']:.3f}, "
                  f"F1={stats['f1']:.3f}, "
                  f"support={stats['support']}")

        return {
            "accuracy": confusion_metrics["accuracy"],
            "per_class": confusion_metrics["per_class"],
            "confusion_matrix": confusion_metrics["confusion_matrix"],
            "labels": labels,
            "test_cases": len(test_cases)
        }

    def evaluate_filter_extraction(self) -> Dict[str, Any]:
        """
        Evaluate filter extraction accuracy.

        Returns:
            Dict with filter extraction metrics
        """
        print("\n" + "=" * 60)
        print("EVALUATING FILTER EXTRACTION")
        print("=" * 60)

        test_cases = self.golden_data.get("filter_extraction", [])
        results = []

        for case in test_cases:
            query_id = case["query_id"]
            query = case["query"]
            expected = case["expected_filters"]

            extracted = extract_filters_rules(query)
            extracted_dict = {
                k: v for k, v in extracted.model_dump().items()
                if v is not None and v != [] and v != ""
            }

            # Check matches
            matches = {}
            for key in ["brand", "category", "price_min", "price_max"]:
                exp_val = expected.get(key)
                ext_val = extracted_dict.get(key)
                if exp_val is not None:
                    matches[key] = (exp_val == ext_val)

            all_correct = all(matches.values()) if matches else True

            status = "✓" if all_correct else "✗"
            print(f"[{query_id}] {status} Query: '{query}'")
            print(f"          Expected: {expected}")
            print(f"          Extracted: {extracted_dict}")

            results.append({
                "query_id": query_id,
                "query": query,
                "expected": expected,
                "extracted": extracted_dict,
                "matches": matches,
                "all_correct": all_correct
            })

        # Calculate accuracy per filter type
        filter_types = ["brand", "category", "price_min", "price_max"]
        accuracies = {}
        for ftype in filter_types:
            correct = sum(1 for r in results if r["matches"].get(ftype, True))
            total = sum(1 for r in results if ftype in r["expected"])
            accuracies[ftype] = correct / total if total > 0 else 1.0

        overall_accuracy = sum(r["all_correct"] for r in results) / len(results) if results else 0.0

        print("\n" + "-" * 60)
        print(f"FILTER EXTRACTION OVERALL ACCURACY: {overall_accuracy:.4f}")
        print("-" * 60)
        print("Per-filter accuracy:")
        for ftype, acc in accuracies.items():
            print(f"  {ftype:15s}: {acc:.4f}")

        return {
            "overall_accuracy": overall_accuracy,
            "per_filter_accuracy": accuracies,
            "per_query": results,
            "num_queries": len(test_cases)
        }

    def evaluate_diversity(self, k_values: List[int] = [3, 5, 8]) -> Dict[str, Any]:
        """
        Evaluate diversity of retrieval results.

        Args:
            k_values: List of K values to evaluate diversity at

        Returns:
            Dict with diversity metrics
        """
        print("\n" + "=" * 60)
        print("EVALUATING RESULT DIVERSITY")
        print("=" * 60)

        test_cases = self.golden_data.get("diversity_tests", [])
        results = []

        for case in test_cases:
            query_id = case["query_id"]
            query = case["query"]
            min_brand_div = case.get("min_brand_diversity", 0.0)
            min_cat_div = case.get("min_category_diversity", 0.0)

            print(f"\n[{query_id}] Query: '{query}'")

            # Search
            scored = self.index.search_by_text(query, top_k=50, filters=FilterSpec())
            retrieved_ids = [self.catalog_df.iloc[i]["id"] for i, _ in scored[:8]]

            # Calculate diversity at different K
            diversity_metrics = {}
            for k in k_values:
                brand_div = diversity_at_k(retrieved_ids, self.catalog_df, k, "brand")
                cat_div = diversity_at_k(retrieved_ids, self.catalog_df, k, "category")
                diversity_metrics[f"brand_diversity@{k}"] = brand_div
                diversity_metrics[f"category_diversity@{k}"] = cat_div

                print(f"  @{k}: Brand diversity={brand_div:.3f}, "
                      f"Category diversity={cat_div:.3f}")

            # Check if meets minimum thresholds
            meets_brand_req = diversity_metrics.get(f"brand_diversity@8", 0) >= min_brand_div
            meets_cat_req = diversity_metrics.get(f"category_diversity@8", 0) >= min_cat_div

            status = "✓" if (meets_brand_req and meets_cat_req) else "✗"
            print(f"  {status} Meets requirements: brand={meets_brand_req}, category={meets_cat_req}")

            results.append({
                "query_id": query_id,
                "query": query,
                "retrieved": retrieved_ids,
                "diversity_metrics": diversity_metrics,
                "meets_requirements": meets_brand_req and meets_cat_req
            })

        # Aggregate
        all_div_metrics = [r["diversity_metrics"] for r in results]
        aggregated = aggregate_metrics(all_div_metrics)

        print("\n" + "-" * 60)
        print("AGGREGATED DIVERSITY METRICS")
        print("-" * 60)
        for metric_name in sorted(aggregated.keys()):
            stats = aggregated[metric_name]
            print(f"{metric_name:25s}: mean={stats['mean']:.4f}")

        return {
            "aggregated": aggregated,
            "per_query": results,
            "num_queries": len(test_cases)
        }

    def evaluate_edge_cases(self) -> Dict[str, Any]:
        """
        Evaluate system behavior on edge cases.

        Returns:
            Dict with edge case results
        """
        print("\n" + "=" * 60)
        print("EVALUATING EDGE CASES")
        print("=" * 60)

        test_cases = self.golden_data.get("edge_cases", [])
        results = []

        for case in test_cases:
            query_id = case["query_id"]
            query = case["query"]
            relevant = set(case.get("relevant_ids", []))
            notes = case.get("notes", "")

            print(f"\n[{query_id}] Query: '{query}'")
            print(f"  Notes: {notes}")

            try:
                filters = extract_filters_rules(query)
                scored = self.index.search_by_text(query, top_k=50, filters=filters)
                retrieved_ids = [self.catalog_df.iloc[i]["id"] for i, _ in scored[:8]]

                print(f"  Retrieved: {retrieved_ids}")

                # Check if relevant items found
                if relevant:
                    found_relevant = any(rid in retrieved_ids for rid in relevant)
                    status = "✓" if found_relevant else "✗"
                    print(f"  {status} Found relevant items: {found_relevant}")
                else:
                    # For cases expecting empty results
                    status = "✓" if len(retrieved_ids) == 0 else "~"
                    print(f"  {status} Returned {len(retrieved_ids)} results (expected 0)")

                results.append({
                    "query_id": query_id,
                    "query": query,
                    "retrieved": retrieved_ids,
                    "expected_relevant": list(relevant),
                    "notes": notes,
                    "graceful": True  # Didn't crash
                })

            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                results.append({
                    "query_id": query_id,
                    "query": query,
                    "error": str(e),
                    "graceful": False
                })

        graceful_rate = sum(1 for r in results if r.get("graceful", False)) / len(results)

        print("\n" + "-" * 60)
        print(f"GRACEFUL HANDLING RATE: {graceful_rate:.4f}")
        print("-" * 60)

        return {
            "graceful_rate": graceful_rate,
            "results": results,
            "num_cases": len(test_cases)
        }

    def benchmark_performance(self, num_iterations: int = 100) -> Dict[str, Any]:
        """
        Benchmark search latency and throughput.

        Args:
            num_iterations: Number of search iterations to run

        Returns:
            Dict with latency percentiles and throughput
        """
        print("\n" + "=" * 60)
        print(f"BENCHMARKING PERFORMANCE ({num_iterations} iterations)")
        print("=" * 60)

        test_queries = [
            "breathable athletic t-shirt",
            "nike running shoes",
            "warm hoodie",
            "hiking backpack"
        ]

        latencies = []

        for _ in range(num_iterations):
            query = test_queries[_ % len(test_queries)]
            filters = extract_filters_rules(query)

            start = time.time()
            scored = self.index.search_by_text(query, top_k=50, filters=filters)
            _ = [self.catalog_df.iloc[i]["id"] for i, _ in scored[:8]]
            latency = time.time() - start

            latencies.append(latency * 1000)  # Convert to ms

        latencies_array = pd.Series(latencies)

        results = {
            "mean_latency_ms": float(latencies_array.mean()),
            "std_latency_ms": float(latencies_array.std()),
            "p50_latency_ms": float(latencies_array.quantile(0.50)),
            "p95_latency_ms": float(latencies_array.quantile(0.95)),
            "p99_latency_ms": float(latencies_array.quantile(0.99)),
            "min_latency_ms": float(latencies_array.min()),
            "max_latency_ms": float(latencies_array.max()),
            "throughput_qps": 1000.0 / float(latencies_array.mean()),
            "num_iterations": num_iterations
        }

        print(f"\nLatency (ms):")
        print(f"  Mean:  {results['mean_latency_ms']:.2f}")
        print(f"  p50:   {results['p50_latency_ms']:.2f}")
        print(f"  p95:   {results['p95_latency_ms']:.2f}")
        print(f"  p99:   {results['p99_latency_ms']:.2f}")
        print(f"\nThroughput: {results['throughput_qps']:.1f} queries/sec")

        return results

    def run_all_evaluations(self) -> Dict[str, Any]:
        """
        Run all evaluation modules.

        Returns:
            Dict with all evaluation results
        """
        self.start_time = datetime.now()

        print("\n" + "=" * 60)
        print("STARTING COMPREHENSIVE EVALUATION")
        print("=" * 60)
        print(f"Start time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        results = {
            "metadata": {
                "start_time": self.start_time.isoformat(),
                "catalog_size": len(self.catalog_df),
                "catalog_path": "data/catalog.csv"
            }
        }

        try:
            results["retrieval"] = self.evaluate_retrieval()
        except Exception as e:
            print(f"\nERROR in retrieval evaluation: {e}")
            results["retrieval"] = {"error": str(e)}

        try:
            results["intent_classification"] = self.evaluate_intent_classification()
        except Exception as e:
            print(f"\nERROR in intent classification: {e}")
            results["intent_classification"] = {"error": str(e)}

        try:
            results["filter_extraction"] = self.evaluate_filter_extraction()
        except Exception as e:
            print(f"\nERROR in filter extraction: {e}")
            results["filter_extraction"] = {"error": str(e)}

        try:
            results["diversity"] = self.evaluate_diversity()
        except Exception as e:
            print(f"\nERROR in diversity evaluation: {e}")
            results["diversity"] = {"error": str(e)}

        try:
            results["edge_cases"] = self.evaluate_edge_cases()
        except Exception as e:
            print(f"\nERROR in edge case evaluation: {e}")
            results["edge_cases"] = {"error": str(e)}

        try:
            results["performance"] = self.benchmark_performance()
        except Exception as e:
            print(f"\nERROR in performance benchmark: {e}")
            results["performance"] = {"error": str(e)}

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        results["metadata"]["end_time"] = self.end_time.isoformat()
        results["metadata"]["duration_seconds"] = duration

        print("\n" + "=" * 60)
        print("EVALUATION COMPLETE")
        print("=" * 60)
        print(f"Duration: {duration:.1f} seconds")

        self.results = results
        return results

    def save_results(self, output_path: str = "evaluation/results/latest.json"):
        """
        Save evaluation results to JSON file.

        Args:
            output_path: Path to save results
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n[Evaluator] Results saved to {output_path}")

        # Save timestamped version too
        timestamp_obj = self.start_time if self.start_time else datetime.now()
        timestamp = timestamp_obj.strftime('%Y%m%d_%H%M%S')
        timestamped_path = output_path.replace("latest.json", f"eval_{timestamp}.json")
        with open(timestamped_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"[Evaluator] Timestamped results saved to {timestamped_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate AI Commerce Agent")
    parser.add_argument("--mode", type=str, default="all",
                       choices=["all", "retrieval", "intent", "filters",
                               "diversity", "performance", "quick"],
                       help="Evaluation mode to run")
    parser.add_argument("--catalog", type=str, default="data/catalog.csv",
                       help="Path to catalog CSV")
    parser.add_argument("--golden", type=str,
                       default="evaluation/datasets/golden_queries.json",
                       help="Path to golden queries JSON")
    parser.add_argument("--output", type=str,
                       default="evaluation/results/latest.json",
                       help="Path to save results JSON")
    parser.add_argument("--report", type=str, default=None,
                       choices=["html", "json", "both"],
                       help="Generate report in specified format")

    args = parser.parse_args()

    # Initialize evaluator
    evaluator = HybridSystemEvaluator(
        catalog_path=args.catalog,
        golden_queries_path=args.golden
    )

    # Run evaluations based on mode
    if args.mode == "all":
        results = evaluator.run_all_evaluations()
    else:
        # For non-"all" modes, set start_time and add metadata
        evaluator.start_time = datetime.now()

        if args.mode == "retrieval":
            results = {"retrieval": evaluator.evaluate_retrieval()}
        elif args.mode == "intent":
            results = {"intent_classification": evaluator.evaluate_intent_classification()}
        elif args.mode == "filters":
            results = {"filter_extraction": evaluator.evaluate_filter_extraction()}
        elif args.mode == "diversity":
            results = {"diversity": evaluator.evaluate_diversity()}
        elif args.mode == "performance":
            results = {"performance": evaluator.benchmark_performance()}
        elif args.mode == "quick":
            # Quick mode: run retrieval and intent only
            results = {
                "retrieval": evaluator.evaluate_retrieval(k_values=[1, 3, 5]),
                "intent_classification": evaluator.evaluate_intent_classification()
            }
        else:
            print(f"Unknown mode: {args.mode}")
            return

        # Add metadata for non-"all" modes
        evaluator.end_time = datetime.now()
        duration = (evaluator.end_time - evaluator.start_time).total_seconds()
        results["metadata"] = {
            "start_time": evaluator.start_time.isoformat(),
            "end_time": evaluator.end_time.isoformat(),
            "duration_seconds": duration,
            "catalog_size": len(evaluator.catalog_df),
            "catalog_path": args.catalog,
            "mode": args.mode
        }
        evaluator.results = results

    evaluator.results = results
    evaluator.save_results(args.output)

    # Generate reports if requested
    if args.report:
        from evaluation.report_generator import ReportGenerator
        generator = ReportGenerator(results)

        if args.report in ["html", "both"]:
            html_path = args.output.replace(".json", ".html")
            generator.generate_html_report(html_path)

        if args.report in ["json", "both"]:
            # JSON already saved above
            print(f"[Report] JSON report at {args.output}")


if __name__ == "__main__":
    main()
