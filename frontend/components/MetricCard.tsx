// Metric cards for eval dashboard
import React from 'react';

type MetricCardProps = {
  label: string;
  value: string | number;
  description?: string;
  color?: string;
  trend?: 'up' | 'down' | 'neutral';
};

export function MetricCard({ label, value, description, color, trend }: MetricCardProps) {
  const bgColor = color || 'bg-gradient-to-br from-blue-500 to-blue-600';

  return (
    <div className={`${bgColor} rounded-lg shadow-lg p-6 text-white transition-transform hover:scale-105`}>
      <div className="text-sm opacity-90 mb-2 font-medium">{label}</div>
      <div className="text-3xl font-bold mb-2 flex items-baseline gap-2">
        {value}
        {trend && (
          <span className="text-sm opacity-75">
            {trend === 'up' && '↑'}
            {trend === 'down' && '↓'}
            {trend === 'neutral' && '→'}
          </span>
        )}
      </div>
      {description && <div className="text-xs opacity-75">{description}</div>}
    </div>
  );
}

type DetailMetricProps = {
  label: string;
  value: string | number;
};

export function DetailMetric({ label, value }: DetailMetricProps) {
  return (
    <div className="border border-neutral-700 rounded-lg p-4 bg-neutral-800/50 hover:border-emerald-500 transition-colors">
      <div className="text-sm text-neutral-400 mb-1">{label}</div>
      <div className="text-xl font-semibold text-neutral-100">{value}</div>
    </div>
  );
}
