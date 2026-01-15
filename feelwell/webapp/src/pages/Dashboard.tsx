import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

interface SafetyMetrics {
  crisisRecall: number
  falseNegatives: number
  overallAccuracy: number
  avgLatencyMs: number
  passesThreshold: boolean
  lastRunId: string | null
  lastRunTime: string | null
}

interface DatasetBreakdown {
  name: string
  total: number
  correct: number
  accuracy: number
  crisisRecall: number
  category: string
}

interface RecentRun {
  run_id: string
  started_at: string
  total_samples: number
  accuracy: number
  crisis_recall: number
  passes_safety: boolean
}

interface ImprovementItem {
  category: string
  issue: string
  severity: 'critical' | 'warning' | 'info'
  suggestion: string
  affectedCases: number
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<SafetyMetrics>({
    crisisRecall: 0,
    falseNegatives: 0,
    overallAccuracy: 0,
    avgLatencyMs: 0,
    passesThreshold: false,
    lastRunId: null,
    lastRunTime: null,
  })
  const [datasetBreakdown, setDatasetBreakdown] = useState<DatasetBreakdown[]>([])
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>([])
  const [improvements, setImprovements] = useState<ImprovementItem[]>([])
  const [loading, setLoading] = useState(true)
  const [apiConnected, setApiConnected] = useState(false)
  const [runningEval, setRunningEval] = useState(false)

  const loadDashboardData = useCallback(async () => {
    try {
      // Check API health
      await api.healthCheck()
      setApiConnected(true)

      // Load recent results
      const resultsData = await api.listResults()
      setRecentRuns(resultsData.results || [])

      // If we have results, load the latest one for metrics
      if (resultsData.results && resultsData.results.length > 0) {
        const latestRunId = resultsData.results[0].run_id
        const details = await api.getResultDetails(latestRunId)
        
        setMetrics({
          crisisRecall: (details as any).crisis_recall || 0,
          falseNegatives: (details as any).false_negative_count || 0,
          overallAccuracy: (details as any).overall_accuracy || 0,
          avgLatencyMs: (details as any).avg_latency_ms || 0,
          passesThreshold: (details as any).passes_safety_threshold || false,
          lastRunId: latestRunId,
          lastRunTime: (details as any).started_at || null,
        })

        // Parse dataset breakdown
        const byDataset = (details as any).metrics_by_dataset || {}
        const breakdown: DatasetBreakdown[] = Object.entries(byDataset).map(([name, data]: [string, any]) => ({
          name: formatDatasetName(name),
          total: data.total || 0,
          correct: data.correct || 0,
          accuracy: data.accuracy || data.pass_rate || 0,
          crisisRecall: data.crisis_recall || 0,
          category: data.category || getCategoryFromName(name),
        }))
        setDatasetBreakdown(breakdown)

        // Generate improvement suggestions
        generateImprovements(details as any, breakdown)
      }
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
      setApiConnected(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboardData()
    // Refresh every 30 seconds
    const interval = setInterval(loadDashboardData, 30000)
    return () => clearInterval(interval)
  }, [loadDashboardData])

  const formatDatasetName = (name: string): string => {
    return name
      .replace('benchmark_', '')
      .replace(/_/g, ' ')
      .split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ')
  }

  const getCategoryFromName = (name: string): string => {
    if (name.includes('crisis')) return 'safety'
    if (name.includes('adversarial')) return 'robustness'
    if (name.includes('false_positive')) return 'accuracy'
    if (name.includes('mental') || name.includes('phq')) return 'clinical'
    return 'general'
  }

  const generateImprovements = (details: any, breakdown: DatasetBreakdown[]) => {
    const items: ImprovementItem[] = []

    // Check crisis recall
    if (details.crisis_recall < 1.0) {
      items.push({
        category: 'Crisis Detection',
        issue: `Crisis recall is ${(details.crisis_recall * 100).toFixed(1)}% (target: 100%)`,
        severity: 'critical',
        suggestion: 'Add missing crisis patterns to semantic_analyzer.py PHQ9_PATTERNS[9]',
        affectedCases: details.false_negative_count || 0,
      })
    }

    // Check adversarial cases
    const adversarial = breakdown.find(d => d.name.toLowerCase().includes('adversarial'))
    if (adversarial && adversarial.accuracy < 0.5) {
      items.push({
        category: 'Coded Language',
        issue: `Adversarial detection at ${(adversarial.accuracy * 100).toFixed(0)}%`,
        severity: 'critical',
        suggestion: 'Expand coded language patterns in config.py CRISIS_KEYWORDS',
        affectedCases: Math.round(adversarial.total * (1 - adversarial.accuracy)),
      })
    }

    // Check clinical decisions
    const clinical = breakdown.find(d => d.name.toLowerCase().includes('clinical'))
    if (clinical && clinical.accuracy < 0.5) {
      items.push({
        category: 'Clinical Parsing',
        issue: `Clinical decision accuracy at ${(clinical.accuracy * 100).toFixed(0)}%`,
        severity: 'warning',
        suggestion: 'Improve clinical text parsing in datasets/clinical_decisions.py',
        affectedCases: Math.round(clinical.total * (1 - clinical.accuracy)),
      })
    }

    // Check caution cases
    const caution = breakdown.find(d => d.name.toLowerCase().includes('caution'))
    if (caution && caution.accuracy < 0.5) {
      items.push({
        category: 'Caution Detection',
        issue: `Caution case accuracy at ${(caution.accuracy * 100).toFixed(0)}%`,
        severity: 'warning',
        suggestion: 'Tune semantic analyzer thresholds for moderate risk',
        affectedCases: Math.round(caution.total * (1 - caution.accuracy)),
      })
    }

    // Check false positives
    const fp = breakdown.find(d => d.name.toLowerCase().includes('false positive'))
    if (fp && fp.accuracy < 0.9) {
      items.push({
        category: 'False Positives',
        issue: `${Math.round(fp.total * (1 - fp.accuracy))} safe messages flagged incorrectly`,
        severity: 'info',
        suggestion: 'Review idiom patterns and context-aware detection',
        affectedCases: Math.round(fp.total * (1 - fp.accuracy)),
      })
    }

    setImprovements(items)
  }

  const runFullEvaluation = async () => {
    setRunningEval(true)
    try {
      const result = await api.runBenchmarks({
        suites: ['crisis_detection', 'adversarial_cases', 'caution_cases', 'false_positives'],
        datasets: ['mentalchat16k', 'phq9_depression', 'clinical_decisions'],
        run_triage: true,
      })
      
      // Poll for completion
      let status = 'running'
      while (status === 'running' || status === 'started') {
        await new Promise(r => setTimeout(r, 1000))
        const runStatus = await api.getRunStatus(result.run_id)
        status = runStatus.status
      }
      
      // Reload dashboard
      await loadDashboardData()
    } catch (error) {
      console.error('Evaluation failed:', error)
    } finally {
      setRunningEval(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500">Loading dashboard...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* API Status Banner */}
      {!apiConnected && (
        <div className="bg-crisis-light border border-crisis rounded-lg p-4 flex items-center gap-3">
          <span className="text-2xl">⚠️</span>
          <div>
            <h2 className="font-semibold text-crisis-dark">API Disconnected</h2>
            <p className="text-sm text-crisis-dark/70">
              Start the backend: <code className="bg-white/50 px-1 rounded">python -m feelwell.evaluation.start_console</code>
            </p>
          </div>
        </div>
      )}

      {/* Safety Status Banner */}
      {apiConnected && (
        <div className={`border rounded-lg p-4 flex items-center justify-between ${
          metrics.passesThreshold 
            ? 'bg-safe-light border-safe' 
            : 'bg-crisis-light border-crisis'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
              metrics.passesThreshold ? 'bg-safe' : 'bg-crisis'
            }`}>
              {metrics.passesThreshold ? (
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
            </div>
            <div>
              <h2 className={`font-semibold ${metrics.passesThreshold ? 'text-safe-dark' : 'text-crisis-dark'}`}>
                Safety Threshold: {metrics.passesThreshold ? 'PASSING' : 'FAILING'}
              </h2>
              <p className={`text-sm ${metrics.passesThreshold ? 'text-safe-dark/70' : 'text-crisis-dark/70'}`}>
                {metrics.passesThreshold 
                  ? 'All crisis detection tests passing. System ready for deployment.'
                  : `${metrics.falseNegatives} false negatives detected. Review required before deployment.`}
              </p>
            </div>
          </div>
          <button
            onClick={runFullEvaluation}
            disabled={runningEval}
            className="px-4 py-2 bg-white/80 hover:bg-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {runningEval ? 'Running...' : '🔄 Re-run Evaluation'}
          </button>
        </div>
      )}

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          label="Crisis Recall"
          value={`${(metrics.crisisRecall * 100).toFixed(1)}%`}
          status={metrics.crisisRecall === 1.0 ? 'good' : 'critical'}
          description="Must be 100%"
          target="100%"
        />
        <MetricCard
          label="False Negatives"
          value={metrics.falseNegatives.toString()}
          status={metrics.falseNegatives === 0 ? 'good' : 'critical'}
          description="Must be 0"
          target="0"
        />
        <MetricCard
          label="Overall Accuracy"
          value={`${(metrics.overallAccuracy * 100).toFixed(1)}%`}
          status={metrics.overallAccuracy >= 0.85 ? 'good' : metrics.overallAccuracy >= 0.7 ? 'warning' : 'critical'}
          description="Target: >85%"
          target="85%"
        />
        <MetricCard
          label="Avg Latency"
          value={`${metrics.avgLatencyMs.toFixed(1)}ms`}
          status={metrics.avgLatencyMs < 50 ? 'good' : metrics.avgLatencyMs < 100 ? 'warning' : 'critical'}
          description="Target: <50ms"
          target="50ms"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-2 gap-6">
        {/* Dataset Performance */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">Performance by Dataset</h3>
          <div className="space-y-3">
            {datasetBreakdown.length > 0 ? (
              datasetBreakdown.map((dataset) => (
                <DatasetBar key={dataset.name} {...dataset} />
              ))
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">
                Run an evaluation to see dataset breakdown
              </p>
            )}
          </div>
        </div>

        {/* Improvement Suggestions */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-4">
            🔧 Suggested Improvements
          </h3>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {improvements.length > 0 ? (
              improvements.map((item, idx) => (
                <ImprovementCard key={idx} {...item} />
              ))
            ) : metrics.passesThreshold ? (
              <div className="text-center py-8 text-safe">
                <span className="text-3xl">✅</span>
                <p className="mt-2 font-medium">All checks passing!</p>
                <p className="text-sm text-slate-500">No improvements needed</p>
              </div>
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">
                Run an evaluation to see suggestions
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Recent Runs */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800">Recent Evaluation Runs</h3>
          <Link to="/results" className="text-sm text-calm-600 hover:text-calm-700">
            View All →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-3 font-medium text-slate-600">Run ID</th>
                <th className="text-left py-2 px-3 font-medium text-slate-600">Time</th>
                <th className="text-right py-2 px-3 font-medium text-slate-600">Samples</th>
                <th className="text-right py-2 px-3 font-medium text-slate-600">Accuracy</th>
                <th className="text-right py-2 px-3 font-medium text-slate-600">Crisis Recall</th>
                <th className="text-center py-2 px-3 font-medium text-slate-600">Status</th>
              </tr>
            </thead>
            <tbody>
              {recentRuns.slice(0, 5).map((run) => (
                <tr key={run.run_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-3 font-mono text-xs text-slate-600">{run.run_id}</td>
                  <td className="py-2 px-3 text-slate-600">
                    {new Date(run.started_at).toLocaleString()}
                  </td>
                  <td className="py-2 px-3 text-right text-slate-600">{run.total_samples}</td>
                  <td className="py-2 px-3 text-right">
                    <span className={`font-medium ${
                      run.accuracy >= 0.85 ? 'text-safe' : 'text-caution'
                    }`}>
                      {(run.accuracy * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">
                    <span className={`font-medium ${
                      run.crisis_recall === 1.0 ? 'text-safe' : 'text-crisis'
                    }`}>
                      {(run.crisis_recall * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      run.passes_safety
                        ? 'bg-safe-light text-safe-dark'
                        : 'bg-crisis-light text-crisis-dark'
                    }`}>
                      {run.passes_safety ? 'PASS' : 'FAIL'}
                    </span>
                  </td>
                </tr>
              ))}
              {recentRuns.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No evaluation runs yet. Click "Re-run Evaluation" to start.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-4 gap-4">
        <Link to="/chat" className="block">
          <ActionCard icon="💬" label="Chat Tester" description="Test messages interactively" />
        </Link>
        <Link to="/benchmarks" className="block">
          <ActionCard icon="📊" label="Run Benchmarks" description="Execute test suites" />
        </Link>
        <Link to="/results" className="block">
          <ActionCard icon="📈" label="View Results" description="Historical analysis" />
        </Link>
        <Link to="/services" className="block">
          <ActionCard icon="🔧" label="Service Status" description="Backend health" />
        </Link>
      </div>
    </div>
  )
}

function MetricCard({ 
  label, 
  value, 
  status, 
  description, 
  target 
}: { 
  label: string
  value: string
  status: 'good' | 'warning' | 'critical'
  description: string
  target: string
}) {
  const statusColors = {
    good: 'bg-safe-light border-safe',
    warning: 'bg-caution-light border-caution',
    critical: 'bg-crisis-light border-crisis',
  }

  const textColors = {
    good: 'text-safe-dark',
    warning: 'text-caution-dark',
    critical: 'text-crisis-dark',
  }

  return (
    <div className={`rounded-lg border-2 p-4 ${statusColors[status]}`}>
      <div className="flex items-center justify-between">
        <p className={`text-sm font-medium ${textColors[status]}`}>{label}</p>
        <span className={`text-xs px-1.5 py-0.5 rounded ${
          status === 'good' ? 'bg-safe/20' : status === 'warning' ? 'bg-caution/20' : 'bg-crisis/20'
        } ${textColors[status]}`}>
          Target: {target}
        </span>
      </div>
      <p className={`text-3xl font-bold mt-2 ${textColors[status]}`}>{value}</p>
      <p className={`text-xs mt-1 opacity-70 ${textColors[status]}`}>{description}</p>
    </div>
  )
}

function DatasetBar({ name, total, correct, accuracy, category }: DatasetBreakdown) {
  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case 'safety': return 'bg-crisis'
      case 'robustness': return 'bg-caution'
      case 'clinical': return 'bg-purple-500'
      default: return 'bg-calm-500'
    }
  }

  const getBarColor = (acc: number) => {
    if (acc >= 0.9) return 'bg-safe'
    if (acc >= 0.7) return 'bg-caution'
    return 'bg-crisis'
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${getCategoryColor(category)}`} />
          <span className="font-medium text-slate-700">{name}</span>
        </div>
        <span className="text-slate-500">{correct}/{total}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all ${getBarColor(accuracy)}`}
          style={{ width: `${accuracy * 100}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-slate-500">
        <span>{(accuracy * 100).toFixed(1)}% accuracy</span>
      </div>
    </div>
  )
}

function ImprovementCard({ category, issue, severity, suggestion, affectedCases }: ImprovementItem) {
  const severityStyles = {
    critical: 'border-crisis bg-crisis-light',
    warning: 'border-caution bg-caution-light',
    info: 'border-slate-300 bg-slate-50',
  }

  const severityIcons = {
    critical: '🚨',
    warning: '⚠️',
    info: 'ℹ️',
  }

  return (
    <div className={`p-3 rounded-lg border ${severityStyles[severity]}`}>
      <div className="flex items-start gap-2">
        <span>{severityIcons[severity]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-800 text-sm">{category}</span>
            <span className="text-xs text-slate-500">({affectedCases} cases)</span>
          </div>
          <p className="text-sm text-slate-600 mt-0.5">{issue}</p>
          <p className="text-xs text-slate-500 mt-1 font-mono bg-white/50 px-1.5 py-0.5 rounded">
            💡 {suggestion}
          </p>
        </div>
      </div>
    </div>
  )
}

function ActionCard({ icon, label, description }: { icon: string; label: string; description: string }) {
  return (
    <div className="p-4 bg-white border border-slate-200 rounded-lg hover:border-calm-300 hover:shadow-sm transition-all cursor-pointer">
      <span className="text-2xl">{icon}</span>
      <p className="font-medium text-slate-700 mt-2">{label}</p>
      <p className="text-xs text-slate-500">{description}</p>
    </div>
  )
}
