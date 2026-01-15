import { useState, useEffect } from 'react'


interface BenchmarkSuite {
  id: string
  name: string
  description: string
  caseCount: number
  category: 'safety' | 'accuracy' | 'robustness' | 'external' | 'internal' | 'clinical'
}

interface TestCase {
  case_id: string
  input_text: string
  expected_risk_level: string
  actual_risk_level?: string
  expected_bypass_llm?: boolean
  actual_bypass_llm?: boolean
  matched_keywords?: string[]
  passed: boolean
  latency_ms?: number
  error?: string
}

interface RunResult {
  suiteId: string
  suiteName: string
  passed: number
  failed: number
  duration: number
  status: 'running' | 'completed' | 'error'
  testCases: TestCase[]
  error?: string
}

const API_BASE = 'http://localhost:8000'

export default function BenchmarkRunner() {
  const [suites, setSuites] = useState<BenchmarkSuite[]>([])
  const [selectedSuites, setSelectedSuites] = useState<Set<string>>(new Set())
  const [runResults, setRunResults] = useState<Map<string, RunResult>>(new Map())
  const [isRunning, setIsRunning] = useState(false)
  const [expandedSuite, setExpandedSuite] = useState<string | null>(null)
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [loading, setLoading] = useState(true)

  // Load benchmarks from API on mount
  useEffect(() => {
    loadBenchmarks()
    checkApiStatus()
  }, [])

  const checkApiStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/health`)
      if (response.ok) {
        setApiStatus('connected')
      } else {
        setApiStatus('disconnected')
      }
    } catch {
      setApiStatus('disconnected')
    }
  }

  const loadBenchmarks = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/benchmarks`)
      if (response.ok) {
        const data = await response.json()
        setSuites(data.benchmarks.map((b: BenchmarkSuite) => ({
          ...b,
          caseCount: (b as any).case_count || b.caseCount,
        })))
      }
    } catch (error) {
      console.error('Failed to load benchmarks:', error)
      // Fallback to hardcoded list
      setSuites([
        { id: 'crisis_detection', name: 'Crisis Detection', description: 'Explicit crisis keyword detection', caseCount: 20, category: 'safety' },
        { id: 'adversarial_cases', name: 'Adversarial Cases', description: 'Bypass attempt detection', caseCount: 20, category: 'robustness' },
        { id: 'false_positives', name: 'False Positives', description: 'Idiom and safe message handling', caseCount: 25, category: 'accuracy' },
        { id: 'caution_cases', name: 'Caution Cases', description: 'Graduated response testing', caseCount: 20, category: 'accuracy' },
      ])
    }
    setLoading(false)
  }

  const toggleSuite = (id: string) => {
    const newSelected = new Set(selectedSuites)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedSuites(newSelected)
  }

  const selectCategory = (category: string) => {
    const categoryIds = suites.filter((s: BenchmarkSuite) =>
      s.category === category ||
      (category === 'safety' && s.id === 'crisis_detection')
    ).map((s: BenchmarkSuite) => s.id)
    setSelectedSuites(new Set(categoryIds))
  }

  const selectAll = () => {
    setSelectedSuites(new Set(suites.map((s: BenchmarkSuite) => s.id)))
  }

  const runSingleBenchmark = async (suiteId: string): Promise<RunResult> => {
    const suite = suites.find((s: BenchmarkSuite) => s.id === suiteId)!
    const startTime = performance.now()
    const testCases: TestCase[] = []

    try {
      // Fetch benchmark cases from API
      const casesResponse = await fetch(`${API_BASE}/api/benchmarks/${suiteId}/cases`)

      if (!casesResponse.ok) {
        throw new Error(`Failed to fetch cases: ${casesResponse.status}`)
      }

      const casesData = await casesResponse.json()
      const cases = casesData.cases || []

      // Run each test case against the real scanner
      for (const testCase of cases) {
        const caseStartTime = performance.now()

        try {
          const scanResponse = await fetch(`${API_BASE}/api/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: testCase.input_text,
              student_id: 'benchmark_test',
              session_id: `bench_${suiteId}`,
            }),
          })

          if (!scanResponse.ok) {
            throw new Error(`Scan failed: ${scanResponse.status}`)
          }

          const scanResult = await scanResponse.json()
          const caseLatency = performance.now() - caseStartTime

          // Compare expected vs actual
          const expectedLevel = testCase.expected_risk_level?.toLowerCase()
          const actualLevel = scanResult.risk_level?.toLowerCase()
          const levelMatch = expectedLevel === actualLevel

          const expectedBypass = testCase.expected_bypass_llm
          const actualBypass = scanResult.bypass_llm
          const bypassMatch = expectedBypass === undefined || expectedBypass === actualBypass

          const passed = levelMatch && bypassMatch

          testCases.push({
            case_id: testCase.case_id,
            input_text: testCase.input_text,
            expected_risk_level: expectedLevel,
            actual_risk_level: actualLevel,
            expected_bypass_llm: expectedBypass,
            actual_bypass_llm: actualBypass,
            matched_keywords: scanResult.matched_keywords || [],
            passed,
            latency_ms: caseLatency,
          })
        } catch (error) {
          testCases.push({
            case_id: testCase.case_id,
            input_text: testCase.input_text,
            expected_risk_level: testCase.expected_risk_level,
            passed: false,
            error: error instanceof Error ? error.message : 'Unknown error',
          })
        }
      }

      const duration = performance.now() - startTime
      const passed = testCases.filter((tc: TestCase) => tc.passed).length
      const failed = testCases.filter((tc: TestCase) => !tc.passed).length

      return {
        suiteId,
        suiteName: suite.name,
        passed,
        failed,
        duration,
        status: 'completed',
        testCases,
      }
    } catch (error) {
      return {
        suiteId,
        suiteName: suite.name,
        passed: 0,
        failed: 0,
        duration: performance.now() - startTime,
        status: 'error',
        testCases: [],
        error: error instanceof Error ? error.message : 'Unknown error',
      }
    }
  }

  const runSelected = async () => {
    if (selectedSuites.size === 0 || apiStatus !== 'connected') return
    setIsRunning(true)
    setExpandedSuite(null)

    for (const suiteId of selectedSuites) {
      const suite = suites.find((s: BenchmarkSuite) => s.id === suiteId)!

      // Set running state
      setRunResults((prev: Map<string, RunResult>) => new Map(prev).set(suiteId, {
        suiteId,
        suiteName: suite.name,
        passed: 0,
        failed: 0,
        duration: 0,
        status: 'running',
        testCases: [],
      }))

      // Run the actual benchmark
      const result = await runSingleBenchmark(suiteId)

      setRunResults((prev: Map<string, RunResult>) => new Map(prev).set(suiteId, result))
    }

    setIsRunning(false)
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'safety': return 'bg-crisis-light text-crisis-dark'
      case 'accuracy': return 'bg-calm-100 text-calm-700'
      case 'robustness': return 'bg-caution-light text-caution-dark'
      case 'external': return 'bg-slate-100 text-slate-700'
      case 'internal': return 'bg-calm-100 text-calm-700'
      case 'clinical': return 'bg-purple-100 text-purple-700'
      default: return 'bg-slate-100 text-slate-700'
    }
  }

  const totalPassed = Array.from(runResults.values()).reduce((sum: number, r: RunResult) => sum + r.passed, 0)
  const totalFailed = Array.from(runResults.values()).reduce((sum: number, r: RunResult) => sum + r.failed, 0)
  const totalDuration = Array.from(runResults.values()).reduce((sum: number, r: RunResult) => sum + r.duration, 0)
  const completedSuites = Array.from(runResults.values()).filter((r: RunResult) => r.status === 'completed').length

  return (
    <div className="space-y-6">
      {/* Header with API Status */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Benchmark Runner</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className={`w-2 h-2 rounded-full ${apiStatus === 'connected' ? 'bg-safe' :
              apiStatus === 'disconnected' ? 'bg-crisis' : 'bg-caution animate-pulse'
              }`} />
            <span className="text-sm text-slate-500">
              {apiStatus === 'connected' ? 'Connected to API (localhost:8000)' :
                apiStatus === 'disconnected' ? 'API Disconnected - Start backend server' :
                  'Checking API...'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => selectCategory('safety')}
            className="px-3 py-1.5 text-sm bg-crisis-light text-crisis-dark rounded-lg hover:bg-crisis/20"
          >
            Safety Critical
          </button>
          <button
            onClick={selectAll}
            className="px-3 py-1.5 text-sm bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200"
          >
            Select All
          </button>
          <button
            onClick={runSelected}
            disabled={selectedSuites.size === 0 || isRunning || apiStatus !== 'connected'}
            className="px-4 py-1.5 text-sm bg-calm-500 text-white rounded-lg hover:bg-calm-600 disabled:opacity-50"
          >
            {isRunning ? 'Running...' : `Run Selected (${selectedSuites.size})`}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-8 text-slate-500">Loading benchmarks...</div>
      )}

      {/* Suites Grid */}
      {!loading && (
        <div className="grid grid-cols-2 gap-4">
          {suites.map((suite: BenchmarkSuite) => {
            const result = runResults.get(suite.id)
            const isSelected = selectedSuites.has(suite.id)
            const isExpanded = expandedSuite === suite.id

            return (
              <div key={suite.id} className="space-y-2">
                <div
                  onClick={() => !isRunning && toggleSuite(suite.id)}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${isSelected
                    ? 'border-calm-500 bg-calm-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-slate-800">{suite.name}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${getCategoryColor(suite.category)}`}>
                          {suite.category}
                        </span>
                      </div>
                      <p className="text-sm text-slate-500 mt-1">{suite.description}</p>
                      <p className="text-xs text-slate-400 mt-2">{suite.caseCount} test cases</p>
                    </div>
                    <div className="text-right">
                      {result?.status === 'running' && (
                        <span className="text-sm text-calm-600 animate-pulse">Running...</span>
                      )}
                      {result?.status === 'completed' && (
                        <div>
                          <span className={`text-lg font-bold ${result.failed === 0 ? 'text-safe' : 'text-crisis'
                            }`}>
                            {result.passed}/{result.passed + result.failed}
                          </span>
                          <p className="text-xs text-slate-400">{result.duration.toFixed(0)}ms</p>
                          {result.testCases.length > 0 && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setExpandedSuite(isExpanded ? null : suite.id)
                              }}
                              className="text-xs text-calm-600 hover:text-calm-700 mt-1"
                            >
                              {isExpanded ? 'Hide Details' : 'View Details'}
                            </button>
                          )}
                        </div>
                      )}
                      {result?.status === 'error' && (
                        <span className="text-sm text-crisis">Error</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Expanded Test Case Details */}
                {isExpanded && result?.testCases && (
                  <div className="bg-white rounded-lg border border-slate-200 p-4 max-h-96 overflow-y-auto">
                    <h4 className="font-medium text-slate-700 mb-3">Test Case Results</h4>
                    <div className="space-y-2">
                      {result.testCases.map((tc: TestCase, idx: number) => (
                        <div
                          key={tc.case_id || idx}
                          className={`p-3 rounded-lg border ${tc.passed
                            ? 'bg-safe-light border-safe/30'
                            : 'bg-crisis-light border-crisis/30'
                            }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className={`text-lg ${tc.passed ? 'text-safe' : 'text-crisis'}`}>
                                  {tc.passed ? '✓' : '✗'}
                                </span>
                                <span className="font-mono text-xs text-slate-500">{tc.case_id}</span>
                              </div>
                              <p className="text-sm text-slate-700 mt-1 truncate" title={tc.input_text}>
                                "{tc.input_text}"
                              </p>
                              <div className="flex flex-wrap gap-2 mt-2 text-xs">
                                <span className="px-2 py-0.5 bg-slate-200 rounded">
                                  Expected: <strong>{tc.expected_risk_level}</strong>
                                </span>
                                <span className={`px-2 py-0.5 rounded ${tc.expected_risk_level === tc.actual_risk_level
                                  ? 'bg-safe/20 text-safe-dark'
                                  : 'bg-crisis/20 text-crisis-dark'
                                  }`}>
                                  Actual: <strong>{tc.actual_risk_level || 'N/A'}</strong>
                                </span>
                                {tc.expected_bypass_llm !== undefined && (
                                  <span className={`px-2 py-0.5 rounded ${tc.expected_bypass_llm === tc.actual_bypass_llm
                                    ? 'bg-safe/20 text-safe-dark'
                                    : 'bg-crisis/20 text-crisis-dark'
                                    }`}>
                                    Bypass: {tc.actual_bypass_llm ? 'Yes' : 'No'}
                                  </span>
                                )}
                                {tc.matched_keywords && tc.matched_keywords.length > 0 && (
                                  <span className="px-2 py-0.5 bg-caution/20 text-caution-dark rounded">
                                    Keywords: {tc.matched_keywords.join(', ')}
                                  </span>
                                )}
                              </div>
                              {tc.error && (
                                <p className="text-xs text-crisis mt-1">Error: {tc.error}</p>
                              )}
                            </div>
                            {tc.latency_ms && (
                              <span className="text-xs text-slate-400 ml-2">
                                {tc.latency_ms.toFixed(0)}ms
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Results Summary */}
      {runResults.size > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="font-semibold text-slate-800 mb-3">Run Summary</h3>
          <div className="grid grid-cols-4 gap-4">
            <div className="text-center p-3 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-slate-800">{completedSuites}</p>
              <p className="text-sm text-slate-500">Suites Run</p>
            </div>
            <div className="text-center p-3 bg-safe-light rounded-lg">
              <p className="text-2xl font-bold text-safe-dark">{totalPassed}</p>
              <p className="text-sm text-safe-dark/70">Tests Passed</p>
            </div>
            <div className="text-center p-3 bg-crisis-light rounded-lg">
              <p className="text-2xl font-bold text-crisis-dark">{totalFailed}</p>
              <p className="text-sm text-crisis-dark/70">Tests Failed</p>
            </div>
            <div className="text-center p-3 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-slate-800">
                {(totalDuration / 1000).toFixed(1)}s
              </p>
              <p className="text-sm text-slate-500">Total Duration</p>
            </div>
          </div>

          {/* Safety Assessment */}
          {totalFailed > 0 && (
            <div className="mt-4 p-3 bg-crisis-light rounded-lg border border-crisis/30">
              <p className="text-sm font-medium text-crisis-dark">
                ⚠️ {totalFailed} test(s) failed - Review failed cases before deployment
              </p>
            </div>
          )}
          {totalFailed === 0 && completedSuites > 0 && (
            <div className="mt-4 p-3 bg-safe-light rounded-lg border border-safe/30">
              <p className="text-sm font-medium text-safe-dark">
                ✅ All tests passed - Safety threshold met
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
