import { useState } from 'react'
import api from '../api/client'

interface Message {
  id: string
  text: string
  sender: 'user' | 'system'
  timestamp: Date
}

interface ScanResult {
  risk_level: 'safe' | 'caution' | 'crisis'
  risk_score: number
  bypass_llm: boolean
  matched_keywords: string[]
  scan_latency_ms: number
  // Layer breakdown
  keyword_risk_score?: number
  semantic_risk_score?: number
  // Semantic analysis
  semantic_analysis?: {
    markers: Array<{
      framework: string
      item: number
      name: string
      severity: number
      matched: string
      critical: boolean
    }>
    phq9_score: number
    gad7_score: number
    semantic_risk_score: number
    risk_factors: string[]
    protective_factors: string[]
    explanation: string
    confidence: number
  }
}

interface ServiceResponse {
  service: string
  status: 'success' | 'error'
  data: Record<string, unknown>
  latency_ms: number
}

export default function ChatTester() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [scanResult, setScanResult] = useState<ScanResult | null>(null)
  const [serviceResponses, setServiceResponses] = useState<ServiceResponse[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [useRealApi, setUseRealApi] = useState(false)

  // Session config
  const [sessionConfig] = useState({
    studentId: 'test_student_001',
    sessionId: `sess_${Date.now()}`,
    schoolId: 'test_school_001',
  })

  const handleSend = async () => {
    if (!input.trim() || isProcessing) return

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      text: input,
      sender: 'user',
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsProcessing(true)

    if (useRealApi) {
      await callRealApi(input)
    } else {
      await simulateScan(input)
    }

    setIsProcessing(false)
  }

  const callRealApi = async (text: string) => {
    try {
      const response = await api.scanMessage({
        message: text,
        student_id: sessionConfig.studentId,
        session_id: sessionConfig.sessionId,
      })

      const result: ScanResult = {
        risk_level: response.risk_level,
        risk_score: response.severity_score ?? response.risk_score,
        bypass_llm: response.bypass_llm,
        matched_keywords: response.matched_keywords,
        scan_latency_ms: response.processing_time_ms,
        keyword_risk_score: response.keyword_risk_score,
        semantic_risk_score: response.semantic_risk_score,
        semantic_analysis: response.semantic_analysis,
      }

      setScanResult(result)

      // Build service responses from pipeline stages
      const responses: ServiceResponse[] = response.pipeline_stages.map((stage) => ({
        service: stage.stage.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        status: stage.status === 'complete' ? 'success' as const : 'error' as const,
        data: stage.details || {},
        latency_ms: stage.time_ms || 0,
      }))

      setServiceResponses(responses)

      const systemMessage: Message = {
        id: `msg_${Date.now()}_sys`,
        text: response.bypass_llm
          ? '⚠️ Crisis detected. LLM bypassed. Crisis protocol activated.'
          : response.risk_level === 'caution'
          ? 'Message processed with elevated monitoring.'
          : 'Message processed normally.',
        sender: 'system',
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, systemMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: `msg_${Date.now()}_err`,
        text: `API Error: ${error instanceof Error ? error.message : 'Unknown error'}. Falling back to mock.`,
        sender: 'system',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
      await simulateScan(text)
    }
  }

  const simulateScan = async (text: string) => {
    // Simulate latency
    await new Promise((r) => setTimeout(r, 100))

    // Simple mock scan logic
    const crisisKeywords = ['kill myself', 'suicide', 'unalive', 'cutting myself', 'hurt myself']
    const cautionKeywords = ['hopeless', 'worthless', 'alone', 'anxious', 'depressed']

    const textLower = text.toLowerCase()
    const matchedCrisis = crisisKeywords.filter((k) => textLower.includes(k))
    const matchedCaution = cautionKeywords.filter((k) => textLower.includes(k))

    let riskLevel: 'safe' | 'caution' | 'crisis' = 'safe'
    let riskScore = 0.1
    let bypassLlm = false

    if (matchedCrisis.length > 0) {
      riskLevel = 'crisis'
      riskScore = 1.0
      bypassLlm = true
    } else if (matchedCaution.length > 0) {
      riskLevel = 'caution'
      riskScore = 0.4 + matchedCaution.length * 0.1
    }

    const result: ScanResult = {
      risk_level: riskLevel,
      risk_score: riskScore,
      bypass_llm: bypassLlm,
      matched_keywords: [...matchedCrisis, ...matchedCaution],
      scan_latency_ms: Math.random() * 10 + 2,
    }

    setScanResult(result)

    // Simulate service responses
    const responses: ServiceResponse[] = [
      {
        service: 'Safety Service',
        status: 'success',
        data: { 
          risk_level: result.risk_level,
          risk_score: result.risk_score,
          matched_keywords: result.matched_keywords,
        },
        latency_ms: result.scan_latency_ms,
      },
    ]

    if (!bypassLlm) {
      responses.push({
        service: 'Observer Service',
        status: 'success',
        data: { risk_score: riskScore + 0.05, markers: [] },
        latency_ms: Math.random() * 20 + 5,
      })
    }

    if (riskLevel === 'crisis') {
      responses.push({
        service: 'Crisis Engine',
        status: 'success',
        data: { crisis_id: `crisis_${Date.now()}`, state: 'notifying' },
        latency_ms: Math.random() * 15 + 3,
      })
    }

    responses.push({
      service: 'Audit Service',
      status: 'success',
      data: { entry_id: `audit_${Date.now()}`, logged: true },
      latency_ms: Math.random() * 5 + 1,
    })

    setServiceResponses(responses)

    // Add system response
    const systemMessage: Message = {
      id: `msg_${Date.now()}_sys`,
      text: bypassLlm
        ? '⚠️ Crisis detected. LLM bypassed. Crisis protocol activated.'
        : riskLevel === 'caution'
        ? 'Message processed with elevated monitoring.'
        : 'Message processed normally.',
      sender: 'system',
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, systemMessage])
  }

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'crisis': return 'text-crisis bg-crisis-light border-crisis'
      case 'caution': return 'text-caution-dark bg-caution-light border-caution'
      default: return 'text-safe-dark bg-safe-light border-safe'
    }
  }

  return (
    <div className="grid grid-cols-2 gap-6 h-[calc(100vh-140px)]">
      {/* Chat Panel */}
      <div className="flex flex-col bg-white rounded-lg border border-slate-200">
        <div className="p-4 border-b border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-800">Interactive Chat Tester</h2>
              <p className="text-sm text-slate-500">Test messages against the safety pipeline</p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={useRealApi}
                onChange={(e) => setUseRealApi(e.target.checked)}
                className="rounded border-slate-300"
              />
              <span className="text-slate-600">Use Real API</span>
            </label>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-slate-400 py-8">
              <p>Send a message to test the safety pipeline</p>
              <p className="text-sm mt-2">Try: "I feel hopeless" or crisis keywords</p>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg max-w-[80%] ${
                msg.sender === 'user'
                  ? 'bg-calm-100 ml-auto'
                  : 'bg-slate-100'
              }`}
            >
              <p className="text-sm text-slate-700">{msg.text}</p>
              <p className="text-xs text-slate-400 mt-1">
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-slate-200">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type a test message..."
              className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-calm-500"
              disabled={isProcessing}
            />
            <button
              onClick={handleSend}
              disabled={isProcessing}
              className="px-4 py-2 bg-calm-500 text-white rounded-lg hover:bg-calm-600 disabled:opacity-50"
            >
              {isProcessing ? 'Processing...' : 'Send'}
            </button>
          </div>
        </div>

        {/* Session Config */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
          <span>Session: {sessionConfig.sessionId}</span>
          <span className="mx-2">|</span>
          <span>Student: {sessionConfig.studentId}</span>
        </div>
      </div>

      {/* Pipeline Inspector */}
      <div className="flex flex-col bg-white rounded-lg border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">Pipeline Inspector</h2>
          <p className="text-sm text-slate-500">Real-time service responses</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Scan Result */}
          {scanResult && (
            <div className={`p-4 rounded-lg border ${getRiskColor(scanResult.risk_level)}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="font-semibold uppercase">{scanResult.risk_level}</span>
                <span className="text-sm">Score: {scanResult.risk_score.toFixed(2)}</span>
              </div>
              <div className="space-y-2 text-sm">
                <p>Bypass LLM: {scanResult.bypass_llm ? '✅ Yes' : '❌ No'}</p>
                <p>Latency: {scanResult.scan_latency_ms.toFixed(1)}ms</p>
                {scanResult.matched_keywords.length > 0 && (
                  <p>Keywords: {scanResult.matched_keywords.join(', ')}</p>
                )}
                
                {/* Layer Breakdown */}
                {(scanResult.keyword_risk_score !== undefined || scanResult.semantic_risk_score !== undefined) && (
                  <div className="mt-3 pt-3 border-t border-current/20">
                    <p className="font-medium mb-2">Layer Breakdown:</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-white/50 p-2 rounded">
                        <span className="text-slate-500">L1 Keywords:</span>
                        <span className="ml-2 font-mono">{(scanResult.keyword_risk_score ?? 0).toFixed(3)}</span>
                      </div>
                      <div className="bg-white/50 p-2 rounded">
                        <span className="text-slate-500">L2 Semantic:</span>
                        <span className="ml-2 font-mono">{(scanResult.semantic_risk_score ?? 0).toFixed(3)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Semantic Analysis Details */}
          {scanResult?.semantic_analysis && (
            <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
              <h3 className="font-semibold text-indigo-800 mb-3">Semantic Analysis</h3>
              
              {/* Clinical Scores */}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="bg-white p-2 rounded text-sm">
                  <span className="text-slate-500">PHQ-9 Est:</span>
                  <span className="ml-2 font-semibold">{scanResult.semantic_analysis.phq9_score}</span>
                  <span className="text-xs text-slate-400 ml-1">
                    ({scanResult.semantic_analysis.phq9_score >= 20 ? 'severe' :
                      scanResult.semantic_analysis.phq9_score >= 15 ? 'mod-severe' :
                      scanResult.semantic_analysis.phq9_score >= 10 ? 'moderate' :
                      scanResult.semantic_analysis.phq9_score >= 5 ? 'mild' : 'minimal'})
                  </span>
                </div>
                <div className="bg-white p-2 rounded text-sm">
                  <span className="text-slate-500">GAD-7 Est:</span>
                  <span className="ml-2 font-semibold">{scanResult.semantic_analysis.gad7_score}</span>
                  <span className="text-xs text-slate-400 ml-1">
                    ({scanResult.semantic_analysis.gad7_score >= 15 ? 'severe' :
                      scanResult.semantic_analysis.gad7_score >= 10 ? 'moderate' :
                      scanResult.semantic_analysis.gad7_score >= 5 ? 'mild' : 'minimal'})
                  </span>
                </div>
              </div>

              {/* Explanation */}
              {scanResult.semantic_analysis.explanation && (
                <div className="bg-white p-2 rounded text-sm mb-3">
                  <p className="text-slate-600">{scanResult.semantic_analysis.explanation}</p>
                </div>
              )}

              {/* Clinical Markers */}
              {scanResult.semantic_analysis.markers.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-medium text-indigo-700 mb-2">Clinical Markers Detected:</p>
                  <div className="space-y-1">
                    {scanResult.semantic_analysis.markers.map((marker, idx) => (
                      <div key={idx} className={`text-xs p-2 rounded ${marker.critical ? 'bg-red-100 border border-red-300' : 'bg-white'}`}>
                        <span className="font-medium">{marker.framework.toUpperCase()}-{marker.item}</span>
                        <span className="text-slate-500 ml-2">{marker.name}</span>
                        <span className="text-slate-400 ml-2">severity: {marker.severity}</span>
                        {marker.critical && <span className="ml-2 text-red-600 font-semibold">⚠️ CRITICAL</span>}
                        <div className="text-slate-400 mt-1">matched: "{marker.matched}"</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk & Protective Factors */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                {scanResult.semantic_analysis.risk_factors.length > 0 && (
                  <div className="bg-red-50 p-2 rounded">
                    <p className="font-medium text-red-700 mb-1">Risk Factors:</p>
                    <ul className="text-red-600 space-y-0.5">
                      {scanResult.semantic_analysis.risk_factors.map((f, i) => (
                        <li key={i}>• {f.replace(/_/g, ' ')}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {scanResult.semantic_analysis.protective_factors.length > 0 && (
                  <div className="bg-green-50 p-2 rounded">
                    <p className="font-medium text-green-700 mb-1">Protective Factors:</p>
                    <ul className="text-green-600 space-y-0.5">
                      {scanResult.semantic_analysis.protective_factors.map((f, i) => (
                        <li key={i}>• {f.replace(/_/g, ' ')}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Confidence */}
              <div className="mt-3 text-xs text-indigo-600">
                Confidence: {(scanResult.semantic_analysis.confidence * 100).toFixed(0)}%
              </div>
            </div>
          )}

          {/* Service Responses */}
          {serviceResponses.map((resp, idx) => (
            <div key={idx} className="p-3 bg-slate-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-slate-700">{resp.service}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  resp.status === 'success' ? 'bg-safe-light text-safe-dark' : 'bg-crisis-light text-crisis-dark'
                }`}>
                  {resp.status}
                </span>
              </div>
              <pre className="text-xs text-slate-600 overflow-x-auto">
                {JSON.stringify(resp.data, null, 2)}
              </pre>
              <p className="text-xs text-slate-400 mt-2">
                Latency: {resp.latency_ms.toFixed(1)}ms
              </p>
            </div>
          ))}

          {!scanResult && (
            <div className="text-center text-slate-400 py-8">
              <p>Send a message to see pipeline responses</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
