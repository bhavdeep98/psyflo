import { useState, useEffect } from 'react'
import api from '../api/client'

interface EvaluationRun {
  run_id: string
  started_at: string
  completed_at?: string
  duration_seconds?: number
  total_samples_evaluated: number
  overall_accuracy: number
  crisis_recall: number
  crisis_precision?: number
  false_negative_count: number
  passes_safety_threshold: boolean
  safety_issues: string[]
  avg_latency_ms?: number
  p99_latency_ms?: number
  metrics_by_dataset: Record<string, DatasetMetrics>
  metrics_by_category?: Record<string, CategoryMetrics>
  // Test Suites
  e2e_results?: TestSuiteResult
  integration_results?: TestSuiteResult
  canary_results?: TestSuiteResult
}

interface DatasetMetrics {
  total: number
  correct: number
  accuracy?: number
  pass_rate?: number
  crisis_tp?: number
  crisis_fp?: number
  crisis_fn?: number
  crisis_recall?: number
  latencies?: number[]
  category?: string
  stats?: {
    total_samples: number
    samples_by_category?: Record<string, number>
    samples_by_triage?: Record<string, number>
  }
}

interface CategoryMetrics {
  category: string
  total: number
  accuracy: number
  crisis_precision?: number
  crisis_recall?: number
}

export default function EvaluationResults() {
  const [runs, setRuns] = useState<EvaluationRun[]>([])
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'datasets' | 'categories' | 'latency' | 'suites'>('overview')

  useEffect(() => {
    loadResults()
  }, [])

  const loadResults = async () => {
    setLoading(true)
    try {
      const data = await api.listResults()
      const runsWithDetails: EvaluationRun[] = []

      // Filter for runs that have BENCHMARKS (ignore suites-only runs)
      const benchmarkRuns = (data.results || []).filter((r: any) => r.has_benchmarks)

      for (const run of benchmarkRuns.slice(0, 10)) {
        try {
          const details = await api.getResultDetails(run.run_id)
          runsWithDetails.push(details as unknown as EvaluationRun)
        } catch {
          // Skip runs that can't be loaded
        }
      }

      setRuns(runsWithDetails)
      if (runsWithDetails.length > 0) {
        setSelectedRun(runsWithDetails[0])
      }
    } catch (error) {
      console.error('Failed to load results:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(1)}%`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">Loading benchmark results...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Benchmark Results</h2>
          <p className="text-sm text-slate-500">Analysis of AI model performance on datasets</p>
        </div>
        <button
          onClick={loadResults}
          className="px-4 py-2 text-sm bg-calm-500 text-white rounded-lg hover:bg-calm-600"
        >
          🔄 Refresh
        </button>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Runs List */}
        <div className="col-span-1 space-y-3">
          <h3 className="font-medium text-slate-700">Recent Runs</h3>
          {runs.length === 0 ? (
            <div className="p-4 bg-slate-50 rounded-lg text-center text-slate-500 text-sm">
              No evaluation runs yet
            </div>
          ) : (
            runs.map((run) => (
              <div
                key={run.run_id}
                onClick={() => setSelectedRun(run)}
                className={`p-4 rounded-lg border cursor-pointer transition-all ${selectedRun?.run_id === run.run_id
                  ? 'border-calm-500 bg-calm-50'
                  : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-slate-600">{run.run_id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${run.passes_safety_threshold
                    ? 'bg-safe-light text-safe-dark'
                    : 'bg-crisis-light text-crisis-dark'
                    }`}>
                    {run.passes_safety_threshold ? 'PASS' : 'FAIL'}
                  </span>
                </div>
                <p className="text-xs text-slate-500">{formatDate(run.started_at)}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500">Accuracy</span>
                    <p className="font-medium text-slate-700">{formatPercent(run.overall_accuracy)}</p>
                  </div>
                  <div>
                    <span className="text-slate-500">Crisis</span>
                    <p className={`font-medium ${run.crisis_recall === 1 ? 'text-safe' : 'text-crisis'}`}>
                      {formatPercent(run.crisis_recall)}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Run Details */}
        <div className="col-span-3">
          {selectedRun ? (
            <div className="space-y-6">
              {/* Summary Header */}
              <div className="bg-white rounded-lg border border-slate-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-slate-800">Run: {selectedRun.run_id}</h3>
                    <p className="text-sm text-slate-500">{formatDate(selectedRun.started_at)}</p>
                  </div>
                  <span className={`px-4 py-2 rounded-lg text-sm font-medium ${selectedRun.passes_safety_threshold
                    ? 'bg-safe-light text-safe-dark'
                    : 'bg-crisis-light text-crisis-dark'
                    }`}>
                    {selectedRun.passes_safety_threshold ? '✅ Safety Passed' : '❌ Safety Failed'}
                  </span>
                </div>

                {/* Safety Issues */}
                {selectedRun.safety_issues && selectedRun.safety_issues.length > 0 && (
                  <div className="mb-4 p-3 bg-crisis-light rounded-lg border border-crisis/30">
                    <p className="text-sm font-medium text-crisis-dark mb-1">⚠️ Safety Issues:</p>
                    {selectedRun.safety_issues.map((issue, i) => (
                      <p key={i} className="text-sm text-crisis-dark">• {issue}</p>
                    ))}
                  </div>
                )}

                {/* Key Metrics */}
                <div className="grid grid-cols-5 gap-4">
                  <MetricBox
                    label="Total Samples"
                    value={selectedRun.total_samples_evaluated.toLocaleString()}
                  />
                  <MetricBox
                    label="Overall Accuracy"
                    value={formatPercent(selectedRun.overall_accuracy)}
                    status={selectedRun.overall_accuracy >= 0.85 ? 'good' : 'warning'}
                  />
                  <MetricBox
                    label="Crisis Recall"
                    value={formatPercent(selectedRun.crisis_recall)}
                    status={selectedRun.crisis_recall === 1.0 ? 'good' : 'critical'}
                  />
                  <MetricBox
                    label="False Negatives"
                    value={selectedRun.false_negative_count.toString()}
                    status={selectedRun.false_negative_count === 0 ? 'good' : 'critical'}
                  />
                  <MetricBox
                    label="Avg Latency"
                    value={`${(selectedRun.avg_latency_ms || 0).toFixed(2)}ms`}
                    status={(selectedRun.avg_latency_ms || 0) < 50 ? 'good' : 'warning'}
                  />
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-2 border-b border-slate-200">
                {(['overview', 'datasets', 'categories', 'latency', 'suites'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === tab
                      ? 'border-calm-500 text-calm-700'
                      : 'border-transparent text-slate-500 hover:text-slate-700'
                      }`}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === 'overview' && (
                <OverviewTab run={selectedRun} />
              )}
              {activeTab === 'datasets' && (
                <DatasetsTab metrics={selectedRun.metrics_by_dataset} />
              )}
              {activeTab === 'categories' && (
                <CategoriesTab metrics={selectedRun.metrics_by_category} />
              )}
              {activeTab === 'latency' && (
                <LatencyTab metrics={selectedRun.metrics_by_dataset} />
              )}
              {activeTab === 'suites' && (
                <TestSuitesTab run={selectedRun} />
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 bg-white rounded-lg border border-slate-200">
              <p className="text-slate-500">Select a run to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricBox({
  label,
  value,
  status
}: {
  label: string
  value: string
  status?: 'good' | 'warning' | 'critical'
}) {
  const bgColors = {
    good: 'bg-safe-light',
    warning: 'bg-caution-light',
    critical: 'bg-crisis-light',
  }

  return (
    <div className={`p-3 rounded-lg ${status ? bgColors[status] : 'bg-slate-50'}`}>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-800">{value}</p>
    </div>
  )
}

function OverviewTab({ run }: { run: EvaluationRun }) {
  const datasets = Object.entries(run.metrics_by_dataset)
  const benchmarks = datasets.filter(([name]) => name.startsWith('benchmark_'))
  const external = datasets.filter(([name]) => !name.startsWith('benchmark_'))

  return (
    <div className="space-y-6">
      {/* Visual Summary */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h4 className="font-semibold text-slate-800 mb-4">Performance Overview</h4>
        <div className="grid grid-cols-2 gap-8">
          {/* Accuracy Gauge */}
          <div className="text-center">
            <div className="relative w-32 h-32 mx-auto">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="64" cy="64" r="56"
                  fill="none"
                  stroke="#e2e8f0"
                  strokeWidth="12"
                />
                <circle
                  cx="64" cy="64" r="56"
                  fill="none"
                  stroke={run.overall_accuracy >= 0.85 ? '#22c55e' : run.overall_accuracy >= 0.7 ? '#f59e0b' : '#ef4444'}
                  strokeWidth="12"
                  strokeDasharray={`${run.overall_accuracy * 352} 352`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-2xl font-bold text-slate-800">
                  {(run.overall_accuracy * 100).toFixed(0)}%
                </span>
              </div>
            </div>
            <p className="mt-2 text-sm font-medium text-slate-600">Overall Accuracy</p>
          </div>

          {/* Crisis Detection Stats */}
          <div>
            <h5 className="font-medium text-slate-700 mb-3">Crisis Detection</h5>
            <div className="space-y-2">
              <StatBar label="Recall" value={run.crisis_recall} target={1.0} />
              <StatBar label="Precision" value={run.crisis_precision || 0} target={0.9} />
              <div className="flex items-center justify-between text-sm mt-3">
                <span className="text-slate-600">False Negatives</span>
                <span className={`font-bold ${run.false_negative_count === 0 ? 'text-safe' : 'text-crisis'}`}>
                  {run.false_negative_count}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Benchmark Results */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h4 className="font-semibold text-slate-800 mb-4">Internal Benchmarks</h4>
        <div className="grid grid-cols-2 gap-4">
          {benchmarks.map(([name, metrics]) => (
            <BenchmarkCard key={name} name={name} metrics={metrics} />
          ))}
        </div>
      </div>

      {/* External Datasets */}
      {external.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h4 className="font-semibold text-slate-800 mb-4">External Datasets</h4>
          <div className="grid grid-cols-3 gap-4">
            {external.map(([name, metrics]) => (
              <ExternalDatasetCard key={name} name={name} metrics={metrics} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatBar({ label, value, target }: { label: string; value: number; target: number }) {
  const percentage = value * 100
  const isGood = value >= target

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-600">{label}</span>
        <span className={`font-medium ${isGood ? 'text-safe' : 'text-crisis'}`}>
          {percentage.toFixed(1)}%
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${isGood ? 'bg-safe' : 'bg-crisis'}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

function BenchmarkCard({ name, metrics }: { name: string; metrics: DatasetMetrics }) {
  const displayName = name.replace('benchmark_', '').replace(/_/g, ' ')
  const accuracy = metrics.accuracy || metrics.pass_rate || 0
  const isGood = accuracy >= 0.9

  return (
    <div className={`p-4 rounded-lg border ${isGood ? 'border-safe/30 bg-safe-light' : 'border-crisis/30 bg-crisis-light'}`}>
      <div className="flex items-center justify-between mb-2">
        <h5 className="font-medium text-slate-800 capitalize">{displayName}</h5>
        <span className={`text-lg font-bold ${isGood ? 'text-safe-dark' : 'text-crisis-dark'}`}>
          {(accuracy * 100).toFixed(0)}%
        </span>
      </div>
      <div className="text-sm text-slate-600">
        <span>{metrics.correct || 0}/{metrics.total} passed</span>
        {metrics.crisis_fn !== undefined && metrics.crisis_fn > 0 && (
          <span className="ml-2 text-crisis font-medium">
            ({metrics.crisis_fn} FN)
          </span>
        )}
      </div>
    </div>
  )
}

function ExternalDatasetCard({ name, metrics }: { name: string; metrics: DatasetMetrics }) {
  const accuracy = metrics.accuracy || 0

  return (
    <div className="p-4 rounded-lg border border-slate-200 bg-white">
      <h5 className="font-medium text-slate-800 capitalize mb-2">
        {name.replace(/_/g, ' ')}
      </h5>
      <div className="text-2xl font-bold text-slate-800 mb-1">
        {(accuracy * 100).toFixed(1)}%
      </div>
      <div className="text-sm text-slate-500">
        {metrics.correct || 0}/{metrics.total} correct
      </div>
      {metrics.stats?.samples_by_triage && (
        <div className="mt-2 flex gap-1">
          {Object.entries(metrics.stats.samples_by_triage).map(([level, count]) => (
            <span key={level} className={`text-xs px-1.5 py-0.5 rounded ${level === 'crisis' ? 'bg-crisis-light text-crisis-dark' :
              level === 'caution' ? 'bg-caution-light text-caution-dark' :
                'bg-safe-light text-safe-dark'
              }`}>
              {level}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function DatasetsTab({ metrics }: { metrics: Record<string, DatasetMetrics> }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="text-left py-3 px-4 font-medium text-slate-600">Dataset</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Total</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Correct</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Accuracy</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Crisis TP</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Crisis FP</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Crisis FN</th>
            <th className="text-right py-3 px-4 font-medium text-slate-600">Recall</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(metrics).map(([name, data]) => {
            const accuracy = data.accuracy || data.pass_rate || 0
            return (
              <tr key={name} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="py-3 px-4 font-medium text-slate-700">
                  {name.replace('benchmark_', '').replace(/_/g, ' ')}
                </td>
                <td className="py-3 px-4 text-right text-slate-600">{data.total}</td>
                <td className="py-3 px-4 text-right text-slate-600">{data.correct || '-'}</td>
                <td className="py-3 px-4 text-right">
                  <span className={`font-medium ${accuracy >= 0.9 ? 'text-safe' : accuracy >= 0.7 ? 'text-caution' : 'text-crisis'
                    }`}>
                    {(accuracy * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="py-3 px-4 text-right text-slate-600">{data.crisis_tp ?? '-'}</td>
                <td className="py-3 px-4 text-right text-slate-600">{data.crisis_fp ?? '-'}</td>
                <td className="py-3 px-4 text-right">
                  <span className={data.crisis_fn && data.crisis_fn > 0 ? 'text-crisis font-bold' : 'text-slate-600'}>
                    {data.crisis_fn ?? '-'}
                  </span>
                </td>
                <td className="py-3 px-4 text-right">
                  {data.crisis_recall !== undefined ? (
                    <span className={`font-medium ${data.crisis_recall === 1 ? 'text-safe' : 'text-crisis'}`}>
                      {(data.crisis_recall * 100).toFixed(0)}%
                    </span>
                  ) : '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CategoriesTab({ metrics }: { metrics?: Record<string, CategoryMetrics> }) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500">
        No category breakdown available for this run
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-4">
      {Object.entries(metrics).map(([name, data]) => (
        <div key={name} className="bg-white rounded-lg border border-slate-200 p-4">
          <h5 className="font-medium text-slate-800 capitalize mb-3">{name}</h5>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Total Samples</span>
              <span className="font-medium">{data.total}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Accuracy</span>
              <span className={`font-medium ${data.accuracy >= 0.8 ? 'text-safe' : 'text-caution'}`}>
                {(data.accuracy * 100).toFixed(1)}%
              </span>
            </div>
            {data.crisis_recall !== undefined && (
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Crisis Recall</span>
                <span className={`font-medium ${data.crisis_recall === 1 ? 'text-safe' : 'text-crisis'}`}>
                  {(data.crisis_recall * 100).toFixed(0)}%
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function LatencyTab({ metrics }: { metrics: Record<string, DatasetMetrics> }) {
  const datasetsWithLatency = Object.entries(metrics).filter(([_, data]) => data.latencies && data.latencies.length > 0)

  if (datasetsWithLatency.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500">
        No latency data available for this run
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {datasetsWithLatency.map(([name, data]) => {
        const latencies = data.latencies || []
        const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length
        const max = Math.max(...latencies)
        const min = Math.min(...latencies)
        const sorted = [...latencies].sort((a, b) => a - b)
        const p50 = sorted[Math.floor(sorted.length * 0.5)]
        const p95 = sorted[Math.floor(sorted.length * 0.95)]
        const p99 = sorted[Math.floor(sorted.length * 0.99)]

        return (
          <div key={name} className="bg-white rounded-lg border border-slate-200 p-4">
            <h5 className="font-medium text-slate-800 capitalize mb-3">
              {name.replace('benchmark_', '').replace(/_/g, ' ')}
            </h5>
            <div className="grid grid-cols-6 gap-4 text-sm">
              <div>
                <span className="text-slate-500">Min</span>
                <p className="font-medium">{min.toFixed(2)}ms</p>
              </div>
              <div>
                <span className="text-slate-500">Avg</span>
                <p className="font-medium">{avg.toFixed(2)}ms</p>
              </div>
              <div>
                <span className="text-slate-500">P50</span>
                <p className="font-medium">{p50.toFixed(2)}ms</p>
              </div>
              <div>
                <span className="text-slate-500">P95</span>
                <p className="font-medium">{p95.toFixed(2)}ms</p>
              </div>
              <div>
                <span className="text-slate-500">P99</span>
                <p className={`font-medium ${p99 > 100 ? 'text-caution' : ''}`}>{p99.toFixed(2)}ms</p>
              </div>
              <div>
                <span className="text-slate-500">Max</span>
                <p className={`font-medium ${max > 100 ? 'text-crisis' : ''}`}>{max.toFixed(2)}ms</p>
              </div>
            </div>
            {/* Simple histogram */}
            <div className="mt-3 flex items-end gap-0.5 h-12">
              {createHistogram(latencies, 20).map((count, i) => (
                <div
                  key={i}
                  className="flex-1 bg-calm-400 rounded-t"
                  style={{ height: `${(count / Math.max(...createHistogram(latencies, 20))) * 100}%` }}
                  title={`${count} samples`}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function createHistogram(values: number[], bins: number): number[] {
  if (values.length === 0) return Array(bins).fill(0)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const binSize = (max - min) / bins || 1
  const histogram = Array(bins).fill(0)
  values.forEach(v => {
    const bin = Math.min(Math.floor((v - min) / binSize), bins - 1)
    histogram[bin]++
  })
  return histogram
}

interface TestSuiteResult {
  passed: number
  failed: number
  total_tests?: number
  total_scenarios?: number
  pass_rate: number
  avg_latency_ms?: number
  avg_crisis_detection_latency_ms?: number
  results?: any[]
  scenario_results?: any[]
}

function TestSuitesTab({ run }: { run: EvaluationRun }) {
  // Check if any suite results exist
  if (!run.e2e_results && !run.integration_results && !run.canary_results) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-slate-500">
        No test suite results available for this run.
        <br />
        <span className="text-sm mt-2">
          Run with <code className="bg-slate-100 px-1 rounded">--suites</code> to include Test Suites.
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* E2E Tests */}
      {run.e2e_results && (
        <TestSuiteCard
          title="End-to-End Tests"
          type="e2e"
          result={run.e2e_results}
        />
      )}

      {/* Integration Tests */}
      {run.integration_results && (
        <TestSuiteCard
          title="Integration Tests"
          type="integration"
          result={run.integration_results}
        />
      )}

      {/* Canary Tests */}
      {run.canary_results && (
        <TestSuiteCard
          title="Canary Tests (Simulated Users)"
          type="canary"
          result={run.canary_results}
        />
      )}
    </div>
  )
}

function TestSuiteCard({ title, type, result }: { title: string, type: 'e2e' | 'integration' | 'canary', result: TestSuiteResult }) {
  const isGood = result.pass_rate === 1.0
  const total = result.total_tests || result.total_scenarios || 0

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <h4 className="font-semibold text-slate-800">{title}</h4>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {result.passed}/{total} Passed
          </span>
          <span className={`px-2 py-1 rounded text-xs font-bold ${isGood ? 'bg-safe-light text-safe-dark' : 'bg-crisis-light text-crisis-dark'}`}>
            {(result.pass_rate * 100).toFixed(0)}% Use
          </span>
        </div>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-4 gap-6 mb-6">
          <div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Pass Rate</span>
            <p className={`text-xl font-bold ${isGood ? 'text-safe' : 'text-crisis'}`}>
              {(result.pass_rate * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Total Cases</span>
            <p className="text-xl font-semibold text-slate-700">{total}</p>
          </div>

          {(type === 'e2e' || type === 'integration') && (
            <div>
              <span className="text-xs text-slate-500 uppercase tracking-wider">Avg Latency</span>
              <p className="text-xl font-semibold text-slate-700">
                {result.avg_latency_ms?.toFixed(1) || '-'} <span className="text-sm text-slate-400">ms</span>
              </p>
            </div>
          )}

          {type === 'canary' && (
            <div>
              <span className="text-xs text-slate-500 uppercase tracking-wider">Crisis Detect Time</span>
              <p className="text-xl font-semibold text-slate-700">
                {result.avg_crisis_detection_latency_ms?.toFixed(1) || '-'} <span className="text-sm text-slate-400">ms</span>
              </p>
            </div>
          )}
        </div>

        {/* Failed Items List */}
        {result.failed > 0 && (
          <div className="bg-crisis-light/30 rounded-lg p-4 border border-crisis-light">
            <h5 className="text-sm font-semibold text-crisis-dark mb-2">Failed Cases</h5>
            <ul className="space-y-1">
              {type === 'canary' && result.scenario_results?.filter((r: any) => !r.passed).map((r: any) => (
                <li key={r.scenario_id} className="text-sm text-slate-700 flex items-center gap-2">
                  <span className="text-crisis">✖</span>
                  <span className="font-mono text-xs">{r.scenario_id}</span>
                  <span>{r.scenario_type}</span>
                </li>
              ))}
              {/* Typical results structure for e2e/integration might need adjustment based on actual JSON */}
              {(type === 'e2e' || type === 'integration') && result.results?.filter((r: any) => r.status === 'failed').map((r: any) => (
                <li key={r.test_id} className="text-sm text-slate-700 flex items-center gap-2">
                  <span className="text-crisis">✖</span>
                  <span className="font-mono text-xs">{r.test_id}</span>
                  <span className="text-slate-500">{r.error_message || 'Validation failed'}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
