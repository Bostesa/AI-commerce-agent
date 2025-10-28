'use client';
// Eval dashboard
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  getEvaluationSummary,
  getEvaluationHistory,
  startEvaluation,
  getEvaluationStatus,
  type EvaluationSummary,
  type EvaluationHistory,
} from '../../lib_api';
import { MetricCard, DetailMetric } from '../../components/MetricCard';
import { LoadingDots } from '../../components/LoadingDots';

export default function EvaluationPage() {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [history, setHistory] = useState<EvaluationHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runningMode, setRunningMode] = useState<string>('');
  const [progress, setProgress] = useState<string>('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, historyData] = await Promise.all([
        getEvaluationSummary().catch(() => null),
        getEvaluationHistory().catch(() => ({ evaluations: [] })),
      ]);
      setSummary(summaryData);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load evaluation data');
    } finally {
      setLoading(false);
    }
  };

  const runEvaluation = async (mode: string) => {
    setRunning(true);
    setRunningMode(mode);
    setError(null);
    setProgress('Starting evaluation...');

    try {
      const { job_id } = await startEvaluation(mode);
      setProgress(`Running ${mode} evaluation...`);

      // Poll for completion
      let attempts = 0;
      const maxAttempts = 300; // 10 minutes (300 * 2s)

      const poll = async () => {
        attempts++;

        if (attempts > maxAttempts) {
          setError('Evaluation timed out after 10 minutes');
          setRunning(false);
          setProgress('');
          return;
        }

        try {
          const status = await getEvaluationStatus(job_id);
          console.log('Evaluation status:', status); // Debug log

          if (status.status === 'completed') {
            setProgress('Complete! Reloading data...');
            await loadData();
            setRunning(false);
            setProgress('');
            return;
          } else if (status.status === 'failed') {
            throw new Error(status.error || 'Evaluation failed');
          } else {
            setProgress(`${status.status}... (attempt ${attempts})`);
            setTimeout(poll, 2000); // Poll again in 2 seconds
          }
        } catch (err) {
          console.error('Polling error:', err); // Debug log
          setError(err instanceof Error ? err.message : 'Status check failed');
          setRunning(false);
          setProgress('');
        }
      };

      // Start polling
      setTimeout(poll, 2000);

    } catch (err) {
      console.error('Evaluation error:', err); // Debug log
      setError(err instanceof Error ? err.message : 'Evaluation failed');
      setRunning(false);
      setProgress('');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <LoadingDots />
          <p className="mt-4 text-neutral-400">Loading evaluation data...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-8">
        <Link href="/" className="text-emerald-500 hover:text-emerald-400 text-sm mb-2 inline-block">
          ← Back to Chat
        </Link>
        <h1 className="text-3xl font-bold">ML Evaluation Dashboard</h1>
        <p className="text-neutral-400 mt-1">Hybrid Text + Image Recommendation System</p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-700/50 text-red-400 px-4 py-3 rounded-lg mb-6">
          <div className="flex items-start">
            <span className="text-xl mr-2">⚠️</span>
            <div>
              <strong>Error:</strong> {error}
              {error.includes('No evaluation results') && (
                <p className="mt-2 text-sm text-red-300">
                  Run your first evaluation using the buttons below.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 mb-6">
        <h2 className="text-2xl font-semibold mb-4">Run Evaluation</h2>
        <p className="text-neutral-400 mb-4">
          Evaluate system performance on retrieval quality, intent classification, and more.
        </p>
        <div className="flex flex-wrap gap-4">
          <button
            onClick={() => runEvaluation('quick')}
            disabled={running}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-neutral-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg transition font-medium"
          >
            {running && runningMode === 'quick' ? 'Running...' : 'Quick Eval (~1s)'}
          </button>
          <button
            onClick={() => runEvaluation('all')}
            disabled={running}
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-neutral-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg transition font-medium"
          >
            {running && runningMode === 'all' ? 'Running...' : 'Full Eval (~5s)'}
          </button>
          <button
            onClick={() => runEvaluation('retrieval')}
            disabled={running}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-neutral-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg transition font-medium"
          >
            {running && runningMode === 'retrieval' ? 'Running...' : 'Retrieval Only'}
          </button>
        </div>
        {progress && (
          <div className="mt-4 flex items-center text-neutral-300">
            <LoadingDots />
            <span className="ml-3">{progress}</span>
          </div>
        )}
      </div>

      {summary && (
        <>
          <h2 className="text-2xl font-semibold mb-4">Key Metrics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <MetricCard
              label="NDCG@5"
              value={summary.key_metrics['ndcg@5']?.toFixed(4) || 'N/A'}
              description="Ranking quality"
              color="bg-gradient-to-br from-blue-500 to-blue-600"
            />
            <MetricCard
              label="Intent Accuracy"
              value={
                summary.key_metrics.intent_accuracy
                  ? `${(summary.key_metrics.intent_accuracy * 100).toFixed(2)}%`
                  : 'N/A'
              }
              description="Classification accuracy"
              color="bg-gradient-to-br from-green-500 to-green-600"
            />
            <MetricCard
              label="Filter Accuracy"
              value={
                summary.key_metrics.filter_accuracy
                  ? `${(summary.key_metrics.filter_accuracy * 100).toFixed(2)}%`
                  : 'N/A'
              }
              description="Filter extraction"
              color="bg-gradient-to-br from-purple-500 to-purple-600"
            />
            <MetricCard
              label="p95 Latency"
              value={
                summary.key_metrics.p95_latency_ms
                  ? `${summary.key_metrics.p95_latency_ms.toFixed(2)}ms`
                  : 'N/A'
              }
              description="Response time"
              color="bg-gradient-to-br from-orange-500 to-orange-600"
            />
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 mb-6">
            <h3 className="text-xl font-semibold mb-4">Detailed Retrieval Metrics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <DetailMetric
                label="Precision@5"
                value={summary.key_metrics['precision@5']?.toFixed(4) || 'N/A'}
              />
              <DetailMetric
                label="Recall@5"
                value={summary.key_metrics['recall@5']?.toFixed(4) || 'N/A'}
              />
              <DetailMetric label="MRR" value={summary.key_metrics.mrr?.toFixed(4) || 'N/A'} />
              <DetailMetric
                label="Throughput"
                value={
                  summary.key_metrics.throughput_qps
                    ? `${summary.key_metrics.throughput_qps.toFixed(1)} q/s`
                    : 'N/A'
                }
              />
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 mb-6">
            <h3 className="text-xl font-semibold mb-4">Evaluation Info</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-neutral-300">
              <div>
                <span className="font-semibold">Last Evaluated:</span>{' '}
                {new Date(summary.metadata.start_time).toLocaleString()}
              </div>
              <div>
                <span className="font-semibold">Catalog:</span> {summary.metadata.catalog_size} products
              </div>
              <div>
                <span className="font-semibold">Duration:</span> {summary.metadata.duration_seconds?.toFixed(1)}s
              </div>
            </div>
          </div>
        </>
      )}

      {history && history.evaluations.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6">
          <h3 className="text-xl font-semibold mb-4">Evaluation History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="border-b-2 border-neutral-700">
                <tr>
                  <th className="py-3 px-4 font-semibold text-neutral-300">Date</th>
                  <th className="py-3 px-4 font-semibold text-neutral-300">NDCG@5</th>
                  <th className="py-3 px-4 font-semibold text-neutral-300">Catalog</th>
                  <th className="py-3 px-4 font-semibold text-neutral-300">Duration</th>
                </tr>
              </thead>
              <tbody>
                {history.evaluations.map((evaluation, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-neutral-800 hover:bg-neutral-800/50 transition-colors"
                  >
                    <td className="py-3 px-4 text-neutral-400">
                      {new Date(evaluation.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-400">
                      {evaluation['ndcg@5']?.toFixed(4) || 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-neutral-400">{evaluation.catalog_size}</td>
                    <td className="py-3 px-4 text-neutral-400">{evaluation.duration_seconds?.toFixed(1)}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-8 text-center text-sm text-neutral-500">
        <p className="mb-2">
          📊 <strong className="text-neutral-400">Metrics:</strong> NDCG@5 &gt; 0.75 good | Intent &gt;
          95% good | p95 &lt; 100ms excellent
        </p>
        <p>
          Details: <code className="bg-neutral-800 px-2 py-1 rounded text-xs text-neutral-400">
            backend/evaluation/results/latest.html
          </code>
        </p>
      </div>
    </div>
  );
}
