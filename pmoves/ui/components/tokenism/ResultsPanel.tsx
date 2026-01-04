/* ═══════════════════════════════════════════════════════════════════════════
   Tokenism Results Panel

   Displays simulation results with metrics and charts.
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { SimulationResult, WeeklyMetrics } from '@/lib/tokenismClient';

interface ResultsPanelProps {
  result?: SimulationResult | null;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  color: 'gold' | 'cyan' | 'green' | 'red' | 'violet';
  trend?: number;
}

const colorClasses = {
  gold: 'border-gold-500/50 text-gold-400 bg-gold-500/5',
  cyan: 'border-cyan-500/50 text-cyan-400 bg-cyan-500/5',
  green: 'border-green-500/50 text-green-400 bg-green-500/5',
  red: 'border-red-500/50 text-red-400 bg-red-500/5',
  violet: 'border-violet-500/50 text-violet-400 bg-violet-500/5',
};

function MetricCard({ title, value, color, trend }: MetricCardProps) {
  const classes = colorClasses[color];

  return (
    <div className={`border p-4 ${classes}`}>
      <div className="text-xs text-gray-500 font-mono uppercase mb-1">{title}</div>
      <div className="font-pixel text-xl">{value}</div>
      {trend !== undefined && (
        <div className={`text-xs mt-1 ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

// Simple SVG sparkline for metrics visualization
interface SparklineProps {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}

function Sparkline({ data, color, width = 200, height = 50 }: SparklineProps) {
  if (data.length < 2) {
    return <div className="text-xs text-gray-600">Insufficient data</div>;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="opacity-80">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function TokenismResultsPanel({ result }: ResultsPanelProps) {
  if (!result) {
    return (
      <div className="flex items-center justify-center h-48 border border-dashed border-gray-700 bg-black/30">
        <div className="text-center">
          <p className="text-gray-500 font-pixel text-sm">No Simulation Results</p>
          <p className="text-xs text-gray-600 mt-2">Run a simulation to see results</p>
        </div>
      </div>
    );
  }

  const { finalAvgWealth, finalGini, systemicRiskScore, weeklyMetrics, scenario, contractType } = result;

  // Calculate trends
  const wealthTrend = weeklyMetrics.length >= 2
    ? ((weeklyMetrics[weeklyMetrics.length - 1].avgWealth - weeklyMetrics[0].avgWealth)
      / weeklyMetrics[0].avgWealth) * 100
    : undefined;

  const giniTrend = weeklyMetrics.length >= 2
    ? ((weeklyMetrics[weeklyMetrics.length - 1].giniCoefficient - weeklyMetrics[0].giniCoefficient)
      / weeklyMetrics[0].giniCoefficient) * 100
    : undefined;

  // Risk level
  const riskLevel = systemicRiskScore < 0.3 ? 'Low' : systemicRiskScore < 0.6 ? 'Medium' : 'High';
  const riskColor = systemicRiskScore < 0.3 ? 'green' : systemicRiskScore < 0.6 ? 'gold' : 'red';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono uppercase text-gray-500">Contract</span>
            <span className="font-pixel text-gold-400">{contractType}</span>
            <span className="text-gray-700">|</span>
            <span className="text-xs font-mono uppercase text-gray-500">Scenario</span>
            <span className="font-pixel text-cyan-400">{scenario}</span>
          </div>
          <div className="text-xs text-gray-600 font-mono mt-1">
            ID: {result.simulationId}
          </div>
        </div>
        <div className={`px-3 py-1 border ${colorClasses[riskColor as keyof typeof colorClasses]}`}>
          <span className="text-xs font-mono uppercase">Risk: {riskLevel}</span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Final Avg Wealth"
          value={`$${finalAvgWealth.toFixed(2)}`}
          color="gold"
          trend={wealthTrend}
        />
        <MetricCard
          title="Gini Coefficient"
          value={finalGini.toFixed(3)}
          color="violet"
          trend={giniTrend}
        />
        <MetricCard
          title="Systemic Risk"
          value={(systemicRiskScore * 100).toFixed(1) + '%'}
          color={riskColor as 'gold' | 'green' | 'red'}
        />
        <MetricCard
          title="Weeks Simulated"
          value={weeklyMetrics.length}
          color="cyan"
        />
      </div>

      {/* Time Series Charts */}
      {weeklyMetrics.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Wealth Over Time */}
          <div className="border border-gray-800 bg-black/30 p-4">
            <h3 className="text-xs font-mono uppercase text-gold-400 mb-3">Average Wealth</h3>
            <Sparkline
              data={weeklyMetrics.map((m) => m.avgWealth)}
              color="#fbbf24"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-2">
              <span>Week 0: ${weeklyMetrics[0].avgWealth.toFixed(0)}</span>
              <span>
                Week {weeklyMetrics.length - 1}: ${weeklyMetrics[weeklyMetrics.length - 1].avgWealth.toFixed(0)}
              </span>
            </div>
          </div>

          {/* Gini Over Time */}
          <div className="border border-gray-800 bg-black/30 p-4">
            <h3 className="text-xs font-mono uppercase text-violet-400 mb-3">Gini Coefficient</h3>
            <Sparkline
              data={weeklyMetrics.map((m) => m.giniCoefficient)}
              color="#a78bfa"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-2">
              <span>Week 0: {weeklyMetrics[0].giniCoefficient.toFixed(3)}</span>
              <span>
                Week {weeklyMetrics.length - 1}: {weeklyMetrics[weeklyMetrics.length - 1].giniCoefficient.toFixed(3)}
              </span>
            </div>
          </div>

          {/* Poverty Rate */}
          <div className="border border-gray-800 bg-black/30 p-4">
            <h3 className="text-xs font-mono uppercase text-red-400 mb-3">Poverty Rate</h3>
            <Sparkline
              data={weeklyMetrics.map((m) => m.povertyRate * 100)}
              color="#f87171"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-2">
              <span>Week 0: {(weeklyMetrics[0].povertyRate * 100).toFixed(1)}%</span>
              <span>
                Week {weeklyMetrics.length - 1}: {(weeklyMetrics[weeklyMetrics.length - 1].povertyRate * 100).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Transaction Volume */}
          <div className="border border-gray-800 bg-black/30 p-4">
            <h3 className="text-xs font-mono uppercase text-cyan-400 mb-3">Transaction Volume</h3>
            <Sparkline
              data={weeklyMetrics.map((m) => m.totalVolume)}
              color="#22d3ee"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-2">
              <span>Week 0: ${weeklyMetrics[0].totalVolume.toFixed(0)}</span>
              <span>
                Week {weeklyMetrics.length - 1}: ${weeklyMetrics[weeklyMetrics.length - 1].totalVolume.toFixed(0)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Interpretation */}
      <div className="border border-gray-800 bg-black/30 p-4">
        <h3 className="text-xs font-mono uppercase text-gray-400 mb-2">Analysis</h3>
        <div className="text-sm text-gray-400 space-y-2">
          <p>
            <span className="text-gold-400">Wealth Distribution:</span>{' '}
            {finalGini < 0.3 ? 'Highly equitable distribution.' :
             finalGini < 0.5 ? 'Moderate inequality level.' :
             'High inequality concentration.'}
          </p>
          <p>
            <span className="text-cyan-400">Risk Assessment:</span>{' '}
            {systemicRiskScore < 0.3 ? 'Low systemic risk. Stable economic conditions.' :
             systemicRiskScore < 0.6 ? 'Moderate risk. Monitor volatility.' :
             'High risk. Vulnerable to shocks.'}
          </p>
          <p>
            <span className="text-violet-400">Economic Health:</span>{' '}
            {weeklyMetrics.length > 1 && finalAvgWealth > weeklyMetrics[0].avgWealth
              ? 'Growing economy with increasing wealth.'
              : 'Stagnant or declining economic conditions.'}
          </p>
        </div>
      </div>
    </div>
  );
}

export default TokenismResultsPanel;
