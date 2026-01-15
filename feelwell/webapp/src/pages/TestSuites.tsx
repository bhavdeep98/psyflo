import { useState, useEffect } from 'react'
import api from '../api/client'

interface EvaluationRun {
    run_id: string
    started_at: string
    completed_at?: string
    total_samples_evaluated: number
    overall_accuracy: number
    crisis_recall: number
    passes_safety_threshold: boolean
    has_suites?: boolean
    // Test Suites
    e2e_results?: TestSuiteResult
    integration_results?: TestSuiteResult
    canary_results?: TestSuiteResult
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

export default function TestSuites() {
    const [runs, setRuns] = useState<EvaluationRun[]>([])
    const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        loadResults()
    }, [])

    const loadResults = async () => {
        setLoading(true)
        try {
            const data = await api.listResults()
            const runsWithDetails: EvaluationRun[] = []

            // Filter strictly for runs that have suites
            const suiteRuns = (data.results || []).filter((r: any) => r.has_suites)

            for (const run of suiteRuns.slice(0, 10)) {
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

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-slate-500">Loading pipeline tests...</div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold text-slate-800">Pipeline Tests</h2>
                    <p className="text-sm text-slate-500">Validation of system logic (E2E, Integration, Canary)</p>
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
                    <h3 className="font-medium text-slate-700">Recent Test Runs</h3>
                    {runs.length === 0 ? (
                        <div className="p-4 bg-slate-50 rounded-lg text-center text-slate-500 text-sm">
                            No pipeline tests found.<br />Run <code>--suites</code>
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
                                    <span className={`text-xs px-2 py-0.5 rounded ${isAllPassed(run)
                                        ? 'bg-safe-light text-safe-dark'
                                        : 'bg-crisis-light text-crisis-dark'
                                        }`}>
                                        {isAllPassed(run) ? 'PASS' : 'FAIL'}
                                    </span>
                                </div>
                                <p className="text-xs text-slate-500">{formatDate(run.started_at)}</p>
                                <div className="mt-2 text-xs text-slate-600">
                                    Runs: {[
                                        run.e2e_results ? 'E2E' : null,
                                        run.integration_results ? 'INT' : null,
                                        run.canary_results ? 'CAN' : null
                                    ].filter(Boolean).join(', ')}
                                </div>
                            </div>
                        ))
                    )}
                </div>

                {/* Run Details */}
                <div className="col-span-3">
                    {selectedRun ? (
                        <div className="space-y-6">
                            <TestSuitesTab run={selectedRun} />
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

function isAllPassed(run: EvaluationRun) {
    const e2e = run.e2e_results ? run.e2e_results.pass_rate === 1 : true
    const int = run.integration_results ? run.integration_results.pass_rate === 1 : true
    const can = run.canary_results ? run.canary_results.pass_rate === 1 : true
    return e2e && int && can
}

// Reuse the components from EvaluationResults or duplicated here for simplicity
function TestSuitesTab({ run }: { run: EvaluationRun }) {
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
                        {(result.pass_rate * 100).toFixed(0)}%
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
