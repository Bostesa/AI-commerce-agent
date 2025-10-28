"""HTML report generator for eval results"""
import json
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path


class ReportGenerator:
    def __init__(self, results: Dict[str, Any]):
        self.results = results

    def _format_metric(self, value: float, metric_type: str = "default") -> str:
        if metric_type == "percent":
            return f"{value * 100:.2f}%"
        elif metric_type == "ms":
            return f"{value:.2f}ms"
        elif metric_type == "qps":
            return f"{value:.1f} q/s"
        else:
            return f"{value:.4f}"

    def _generate_summary_section(self) -> str:
        metadata = self.results.get("metadata", {})
        retrieval = self.results.get("retrieval", {})
        intent = self.results.get("intent_classification", {})
        filters = self.results.get("filter_extraction", {})
        performance = self.results.get("performance", {})

        # Extract key metrics
        key_metrics = []

        if retrieval and "aggregated" in retrieval:
            agg = retrieval["aggregated"]
            if "precision@5" in agg:
                key_metrics.append(("Precision@5", self._format_metric(agg["precision@5"]["mean"])))
            if "ndcg@5" in agg:
                key_metrics.append(("NDCG@5", self._format_metric(agg["ndcg@5"]["mean"])))
            if "mrr" in agg:
                key_metrics.append(("MRR", self._format_metric(agg["mrr"]["mean"])))

        if intent and "accuracy" in intent:
            key_metrics.append(("Intent Accuracy", self._format_metric(intent["accuracy"], "percent")))

        if filters and "overall_accuracy" in filters:
            key_metrics.append(("Filter Accuracy", self._format_metric(filters["overall_accuracy"], "percent")))

        if performance:
            if "p95_latency_ms" in performance:
                key_metrics.append(("p95 Latency", self._format_metric(performance["p95_latency_ms"], "ms")))
            if "throughput_qps" in performance:
                key_metrics.append(("Throughput", self._format_metric(performance["throughput_qps"], "qps")))

        metrics_html = "\n".join([
            f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>'
            for label, value in key_metrics
        ])

        duration = metadata.get("duration_seconds", 0)
        start_time = metadata.get("start_time", "")

        return f"""
        <section class="summary">
            <h2>Executive Summary</h2>
            <div class="info-grid">
                <div><strong>Evaluation Date:</strong> {start_time}</div>
                <div><strong>Duration:</strong> {duration:.1f}s</div>
                <div><strong>Catalog Size:</strong> {metadata.get('catalog_size', 'N/A')} products</div>
            </div>
            <h3>Key Metrics</h3>
            <div class="metrics-grid">
                {metrics_html}
            </div>
        </section>
        """

    def _generate_retrieval_section(self) -> str:
        """Generate retrieval quality section."""
        retrieval = self.results.get("retrieval", {})
        if not retrieval or "error" in retrieval:
            return f'<section><h2>Retrieval Quality</h2><p class="error">Error: {retrieval.get("error", "Not evaluated")}</p></section>'

        aggregated = retrieval.get("aggregated", {})

        # Build metrics table
        rows = []
        metrics_order = [
            "precision@1", "precision@3", "precision@5", "precision@8",
            "recall@1", "recall@3", "recall@5", "recall@8",
            "ndcg@1", "ndcg@3", "ndcg@5", "ndcg@8",
            "mrr", "map"
        ]

        for metric_name in metrics_order:
            if metric_name in aggregated:
                stats = aggregated[metric_name]
                rows.append(f"""
                <tr>
                    <td>{metric_name}</td>
                    <td>{self._format_metric(stats['mean'])}</td>
                    <td>{self._format_metric(stats['std'])}</td>
                    <td>{self._format_metric(stats['min'])}</td>
                    <td>{self._format_metric(stats['max'])}</td>
                </tr>
                """)

        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Mean</th>
                    <th>Std Dev</th>
                    <th>Min</th>
                    <th>Max</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

        # Per-query results
        per_query = retrieval.get("per_query", [])
        per_query_rows = []
        for result in per_query[:10]:  # Show first 10
            query = result["query"][:60] + "..." if len(result["query"]) > 60 else result["query"]
            metrics = result["metrics"]
            per_query_rows.append(f"""
            <tr>
                <td><code>{result['query_id']}</code></td>
                <td>{query}</td>
                <td>{self._format_metric(metrics.get('precision@5', 0))}</td>
                <td>{self._format_metric(metrics.get('recall@5', 0))}</td>
                <td>{self._format_metric(metrics.get('ndcg@5', 0))}</td>
                <td>{self._format_metric(metrics.get('mrr', 0))}</td>
            </tr>
            """)

        per_query_html = f"""
        <h3>Sample Per-Query Results (Top 10)</h3>
        <table>
            <thead>
                <tr>
                    <th>Query ID</th>
                    <th>Query</th>
                    <th>P@5</th>
                    <th>R@5</th>
                    <th>NDCG@5</th>
                    <th>MRR</th>
                </tr>
            </thead>
            <tbody>
                {"".join(per_query_rows)}
            </tbody>
        </table>
        """

        return f"""
        <section>
            <h2>Retrieval Quality</h2>
            <p>Evaluated on {retrieval.get('num_evaluated', 0)} queries</p>
            <h3>Aggregated Metrics</h3>
            {table_html}
            {per_query_html if per_query_rows else ""}
        </section>
        """

    def _generate_intent_section(self) -> str:
        """Generate intent classification section."""
        intent = self.results.get("intent_classification", {})
        if not intent or "error" in intent:
            return f'<section><h2>Intent Classification</h2><p class="error">Error: {intent.get("error", "Not evaluated")}</p></section>'

        accuracy = intent.get("accuracy", 0)
        per_class = intent.get("per_class", {})

        # Per-class table
        rows = []
        for label, stats in per_class.items():
            rows.append(f"""
            <tr>
                <td>{label}</td>
                <td>{self._format_metric(stats['precision'])}</td>
                <td>{self._format_metric(stats['recall'])}</td>
                <td>{self._format_metric(stats['f1'])}</td>
                <td>{stats['support']}</td>
            </tr>
            """)

        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Intent Type</th>
                    <th>Precision</th>
                    <th>Recall</th>
                    <th>F1 Score</th>
                    <th>Support</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

        return f"""
        <section>
            <h2>Intent Classification</h2>
            <div class="metric-highlight">Overall Accuracy: {self._format_metric(accuracy, 'percent')}</div>
            <h3>Per-Class Metrics</h3>
            {table_html}
        </section>
        """

    def _generate_filter_section(self) -> str:
        """Generate filter extraction section."""
        filters = self.results.get("filter_extraction", {})
        if not filters or "error" in filters:
            return f'<section><h2>Filter Extraction</h2><p class="error">Error: {filters.get("error", "Not evaluated")}</p></section>'

        overall = filters.get("overall_accuracy", 0)
        per_filter = filters.get("per_filter_accuracy", {})

        # Per-filter table
        rows = []
        for filter_type, accuracy in per_filter.items():
            rows.append(f"""
            <tr>
                <td>{filter_type}</td>
                <td>{self._format_metric(accuracy, 'percent')}</td>
            </tr>
            """)

        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Filter Type</th>
                    <th>Accuracy</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

        return f"""
        <section>
            <h2>Filter Extraction</h2>
            <div class="metric-highlight">Overall Accuracy: {self._format_metric(overall, 'percent')}</div>
            <h3>Per-Filter Accuracy</h3>
            {table_html}
        </section>
        """

    def _generate_diversity_section(self) -> str:
        """Generate diversity metrics section."""
        diversity = self.results.get("diversity", {})
        if not diversity or "error" in diversity:
            return f'<section><h2>Result Diversity</h2><p class="error">Error: {diversity.get("error", "Not evaluated")}</p></section>'

        aggregated = diversity.get("aggregated", {})

        rows = []
        for metric_name in sorted(aggregated.keys()):
            stats = aggregated[metric_name]
            rows.append(f"""
            <tr>
                <td>{metric_name}</td>
                <td>{self._format_metric(stats['mean'])}</td>
            </tr>
            """)

        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Diversity Metric</th>
                    <th>Mean Score</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

        return f"""
        <section>
            <h2>Result Diversity</h2>
            <p>Evaluated on {diversity.get('num_queries', 0)} queries</p>
            {table_html}
        </section>
        """

    def _generate_performance_section(self) -> str:
        """Generate performance benchmark section."""
        performance = self.results.get("performance", {})
        if not performance or "error" in performance:
            return f'<section><h2>Performance Benchmark</h2><p class="error">Error: {performance.get("error", "Not evaluated")}</p></section>'

        metrics = [
            ("Mean Latency", performance.get("mean_latency_ms", 0), "ms"),
            ("p50 Latency", performance.get("p50_latency_ms", 0), "ms"),
            ("p95 Latency", performance.get("p95_latency_ms", 0), "ms"),
            ("p99 Latency", performance.get("p99_latency_ms", 0), "ms"),
            ("Min Latency", performance.get("min_latency_ms", 0), "ms"),
            ("Max Latency", performance.get("max_latency_ms", 0), "ms"),
            ("Throughput", performance.get("throughput_qps", 0), "qps"),
        ]

        rows = []
        for label, value, metric_type in metrics:
            rows.append(f"""
            <tr>
                <td>{label}</td>
                <td>{self._format_metric(value, metric_type)}</td>
            </tr>
            """)

        table_html = f"""
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

        return f"""
        <section>
            <h2>Performance Benchmark</h2>
            <p>Based on {performance.get('num_iterations', 0)} iterations</p>
            {table_html}
        </section>
        """

    def generate_html_report(self, output_path: str):
        """
        Generate complete HTML report.

        Args:
            output_path: Path to save HTML file
        """
        # Generate all sections
        summary = self._generate_summary_section()
        retrieval = self._generate_retrieval_section()
        intent = self._generate_intent_section()
        filters = self._generate_filter_section()
        diversity = self._generate_diversity_section()
        performance = self._generate_performance_section()

        # Complete HTML document
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Commerce Agent - Evaluation Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2.5em;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
        }}

        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }}

        h3 {{
            color: #7f8c8d;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}

        section {{
            margin-bottom: 40px;
        }}

        .summary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 40px;
        }}

        .summary h2, .summary h3 {{
            color: white;
            border-bottom: 2px solid rgba(255,255,255,0.3);
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .metric-card {{
            background: rgba(255, 255, 255, 0.15);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            backdrop-filter: blur(10px);
        }}

        .metric-label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }}

        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
        }}

        .metric-highlight {{
            background: #3498db;
            color: white;
            padding: 15px 20px;
            border-radius: 6px;
            display: inline-block;
            font-size: 1.2em;
            font-weight: bold;
            margin: 15px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        thead {{
            background: #34495e;
            color: white;
        }}

        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}

        tbody tr:hover {{
            background: #f8f9fa;
        }}

        tbody tr:nth-child(even) {{
            background: #fafafa;
        }}

        code {{
            background: #ecf0f1;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        .error {{
            color: #e74c3c;
            background: #fadbd8;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #e74c3c;
        }}

        .footer {{
            margin-top: 60px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AI Commerce Agent - Evaluation Report</h1>
        <p style="color: #7f8c8d; margin-bottom: 20px;">Hybrid Text + Image Recommendation System</p>

        {summary}
        {retrieval}
        {intent}
        {filters}
        {diversity}
        {performance}

        <div class="footer">
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>AI Commerce Agent Evaluation Framework</p>
        </div>
    </div>
</body>
</html>
        """

        # Save HTML file
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"[Report] HTML report generated: {output_path}")
        print(f"[Report] Open in browser: file://{Path(output_path).absolute()}")
