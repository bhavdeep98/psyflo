/**
 * API client for the Feelwell Evaluation Platform.
 * Connects the webapp to the Python backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ScanRequest {
  message: string
  student_id?: string
  session_id?: string
}

export interface SemanticMarker {
  framework: string
  item: number
  name: string
  severity: number
  matched: string
  critical: boolean
}

export interface SemanticAnalysis {
  markers: SemanticMarker[]
  phq9_score: number
  gad7_score: number
  semantic_risk_score: number
  risk_factors: string[]
  protective_factors: string[]
  explanation: string
  confidence: number
}

export interface ScanResponse {
  message_id: string
  risk_level: 'safe' | 'caution' | 'crisis'
  bypass_llm: boolean
  matched_keywords: string[]
  risk_score: number
  processing_time_ms: number
  pipeline_stages: PipelineStage[]
  // Layer breakdown
  keyword_risk_score?: number
  semantic_risk_score?: number
  // Semantic analysis
  semantic_analysis?: SemanticAnalysis
  // Alias for backward compatibility
  severity_score?: number
}

export interface PipelineStage {
  stage: string
  status: string
  time_ms?: number
  details?: Record<string, unknown>
}

export interface BenchmarkSuite {
  id: string
  name: string
  description: string
  case_count: number
  category: 'internal' | 'clinical' | 'external'
}

export interface EvaluationResult {
  run_id: string
  started_at: string
  total_samples: number
  accuracy: number
  crisis_recall: number
  passes_safety: boolean
}

export interface ServiceStatus {
  name: string
  display_name: string
  status: 'healthy' | 'degraded' | 'down' | 'unavailable'
  version: string
  endpoints: string[]
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.fetch('/health')
  }

  async scanMessage(request: ScanRequest): Promise<ScanResponse> {
    const response = await this.fetch<ScanResponse>('/api/scan', {
      method: 'POST',
      body: JSON.stringify(request),
    })
    // Add severity_score alias for backward compatibility
    return {
      ...response,
      severity_score: response.risk_score,
    }
  }

  async listBenchmarks(): Promise<{ benchmarks: BenchmarkSuite[] }> {
    return this.fetch('/api/benchmarks')
  }

  async runBenchmarks(config: {
    suites?: string[]
    datasets?: string[]
    max_samples?: number
    run_triage?: boolean
    run_test_suites?: boolean
  }): Promise<{ run_id: string; status: string }> {
    return this.fetch('/api/benchmarks/run', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  async getRunStatus(runId: string): Promise<{
    run_id: string
    status: string
    progress: number
    started_at: string
    completed_at?: string
    results?: Record<string, unknown>
  }> {
    return this.fetch(`/api/benchmarks/run/${runId}`)
  }

  async listResults(): Promise<{ results: EvaluationResult[] }> {
    return this.fetch('/api/results')
  }

  async getResultDetails(runId: string): Promise<Record<string, unknown>> {
    return this.fetch(`/api/results/${runId}`)
  }

  async getServicesStatus(): Promise<{ services: ServiceStatus[]; timestamp: string }> {
    return this.fetch('/api/services')
  }

  async evaluateLongitudinal(config: {
    num_samples?: number
    use_real_data?: boolean
    data_path?: string
  }): Promise<{
    run_id: string
    metrics: {
      total_students: number
      pattern_accuracy: number
      early_warning_precision: number
      early_warning_recall: number
    }
    sample_predictions: Array<{
      student_id_hash: string
      predicted_pattern: string
      confidence: number
      early_warning_score: number
      risk_factors: string[]
      recommended_intervention: string
    }>
    total_evaluated: number
    pattern_accuracy: number
  }> {
    const params = new URLSearchParams()
    if (config.num_samples) params.append('num_samples', config.num_samples.toString())
    if (config.use_real_data) params.append('use_real_data', 'true')
    if (config.data_path) params.append('data_path', config.data_path)
    return this.fetch(`/api/longitudinal/evaluate?${params}`, { method: 'POST' })
  }

  async getLongitudinalPatterns(): Promise<{
    patterns: Array<{
      id: string
      name: string
      description: string
    }>
  }> {
    return this.fetch('/api/longitudinal/patterns')
  }

  async evaluateClinicalMetrics(
    inputText: string,
    responseText: string
  ): Promise<{
    overall_score: number
    average_score: number
    metrics: Record<string, {
      metric: string
      score: number
      indicators: string[]
      explanation: string
    }>
  }> {
    const params = new URLSearchParams()
    params.append('input_text', inputText)
    params.append('response_text', responseText)
    return this.fetch(`/api/clinical/evaluate?${params}`, { method: 'POST' })
  }

  async getClinicalMetrics(): Promise<{
    metrics: Array<{
      id: string
      name: string
      description: string
      weight: number
    }>
  }> {
    return this.fetch('/api/clinical/metrics')
  }
}

export const api = new ApiClient()
export default api
