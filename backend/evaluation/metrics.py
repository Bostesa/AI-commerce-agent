"""Standard IR metrics for eval"""
from typing import List, Set, Dict, Any
import numpy as np
from collections import defaultdict


def precision_at_k(relevant: Set[str], retrieved: List[str], k: int) -> float:
    """What fraction of top K results are relevant"""
    if k <= 0 or not retrieved:
        return 0.0
    top_k = retrieved[:k]
    relevant_in_top_k = sum(1 for item in top_k if item in relevant)
    return relevant_in_top_k / k


def recall_at_k(relevant: Set[str], retrieved: List[str], k: int) -> float:
    """What fraction of relevant items did we find in top K"""
    if not relevant or k <= 0:
        return 0.0
    top_k = retrieved[:k]
    relevant_in_top_k = sum(1 for item in top_k if item in relevant)
    return relevant_in_top_k / len(relevant)


def f1_at_k(relevant: Set[str], retrieved: List[str], k: int) -> float:
    """Harmonic mean of precision and recall"""
    prec = precision_at_k(relevant, retrieved, k)
    rec = recall_at_k(relevant, retrieved, k)
    if prec + rec == 0:
        return 0.0
    return 2 * (prec * rec) / (prec + rec)


def mean_reciprocal_rank(relevant: Set[str], retrieved: List[str]) -> float:
    """Reciprocal of rank of first relevant item"""
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(relevant: Set[str], retrieved: List[str], k: int,
               relevance_scores: Dict[str, float] = None) -> float:
    """NDCG - accounts for position (higher = better)"""
    if k <= 0 or not retrieved:
        return 0.0

    top_k = retrieved[:k]

    # DCG - actual score
    dcg = 0.0
    for i, item in enumerate(top_k, start=1):
        if item in relevant:
            rel_score = relevance_scores.get(item, 1.0) if relevance_scores else 1.0
            dcg += rel_score / np.log2(i + 1)

    # IDCG - ideal score
    if relevance_scores:
        ideal_scores = sorted([relevance_scores.get(item, 0) for item in relevant], reverse=True)
    else:
        ideal_scores = [1.0] * len(relevant)

    idcg = 0.0
    for i, score in enumerate(ideal_scores[:k], start=1):
        idcg += score / np.log2(i + 1)

    return dcg / idcg if idcg > 0 else 0.0


def mean_average_precision(relevant: Set[str], retrieved: List[str]) -> float:
    """MAP - mean of precision at each relevant position"""
    if not relevant:
        return 0.0

    precisions = []
    num_relevant_seen = 0

    for i, item in enumerate(retrieved, start=1):
        if item in relevant:
            num_relevant_seen += 1
            precisions.append(num_relevant_seen / i)

    return sum(precisions) / len(relevant) if precisions else 0.0


def hit_rate_at_k(relevant: Set[str], retrieved: List[str], k: int) -> float:
    """Did we get at least one hit in top K"""
    top_k = retrieved[:k]
    return 1.0 if any(item in relevant for item in top_k) else 0.0


def diversity_at_k(retrieved: List[str], catalog_df, k: int,
                   dimension: str = "category") -> float:
    """How diverse are results (unique brands/categories)"""
    if k <= 0 or not retrieved:
        return 0.0

    top_k = retrieved[:k]
    values = []
    for pid in top_k:
        rows = catalog_df[catalog_df["id"] == pid]
        if not rows.empty:
            val = rows.iloc[0].get(dimension, "")
            if val:
                values.append(str(val).lower())

    if not values:
        return 0.0

    unique_count = len(set(values))
    return unique_count / min(k, len(values))


def category_coverage(retrieved: List[str], catalog_df,
                      expected_category: str = None) -> float:
    """Fraction of results in the expected category"""
    if not expected_category or not retrieved:
        return 1.0

    in_category = 0
    for pid in retrieved:
        rows = catalog_df[catalog_df["id"] == pid]
        if not rows.empty:
            cat = str(rows.iloc[0].get("category", "")).lower()
            if expected_category.lower() in cat:
                in_category += 1

    return in_category / len(retrieved) if retrieved else 0.0


def calculate_all_metrics(relevant: Set[str], retrieved: List[str],
                          catalog_df, k_values: List[int] = [1, 3, 5, 8],
                          expected_category: str = None) -> Dict[str, Any]:
    """Run all metrics for a query"""
    metrics = {}

    for k in k_values:
        metrics[f"precision@{k}"] = precision_at_k(relevant, retrieved, k)
        metrics[f"recall@{k}"] = recall_at_k(relevant, retrieved, k)
        metrics[f"f1@{k}"] = f1_at_k(relevant, retrieved, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(relevant, retrieved, k)
        metrics[f"hit_rate@{k}"] = hit_rate_at_k(relevant, retrieved, k)
        metrics[f"diversity_category@{k}"] = diversity_at_k(retrieved, catalog_df, k, "category")
        metrics[f"diversity_brand@{k}"] = diversity_at_k(retrieved, catalog_df, k, "brand")

    metrics["mrr"] = mean_reciprocal_rank(relevant, retrieved)
    metrics["map"] = mean_average_precision(relevant, retrieved)

    if expected_category:
        metrics["category_coverage"] = category_coverage(retrieved, catalog_df, expected_category)

    return metrics


def aggregate_metrics(all_query_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results across queries"""
    if not all_query_metrics:
        return {}

    metric_values = defaultdict(list)
    for query_metrics in all_query_metrics:
        for metric_name, value in query_metrics.items():
            if isinstance(value, (int, float)):
                metric_values[metric_name].append(value)

    aggregated = {}
    for metric_name, values in metric_values.items():
        values_array = np.array(values)
        aggregated[metric_name] = {
            "mean": float(np.mean(values_array)),
            "std": float(np.std(values_array)),
            "min": float(np.min(values_array)),
            "max": float(np.max(values_array)),
            "median": float(np.median(values_array)),
        }

    return aggregated


def confusion_matrix_metrics(y_true: List[str], y_pred: List[str],
                             labels: List[str]) -> Dict[str, Any]:
    """Confusion matrix + per-class metrics for classification"""
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return {}

    label_to_idx = {label: i for i, label in enumerate(labels)}
    n = len(labels)
    conf_matrix = np.zeros((n, n), dtype=int)

    for true_label, pred_label in zip(y_true, y_pred):
        if true_label in label_to_idx and pred_label in label_to_idx:
            i = label_to_idx[true_label]
            j = label_to_idx[pred_label]
            conf_matrix[i, j] += 1

    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / len(y_true)

    per_class = {}
    for i, label in enumerate(labels):
        tp = conf_matrix[i, i]
        fp = conf_matrix[:, i].sum() - tp
        fn = conf_matrix[i, :].sum() - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(conf_matrix[i, :].sum())
        }

    return {
        "accuracy": accuracy,
        "confusion_matrix": conf_matrix.tolist(),
        "per_class": per_class,
        "labels": labels
    }
