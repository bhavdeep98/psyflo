import { useState, useEffect } from 'react'

interface ServiceInfo {
  name: string
  displayName: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  latency_ms?: number
  last_check: string
  version?: string
  endpoints: EndpointInfo[]
  metrics: ServiceMetrics
}

interface EndpointInfo {
  path: string
  method: string
  status: 'ok' | 'error'
  latency_ms: number
}

interface ServiceMetrics {
  requests_24h: number
  errors_24h: number
  avg_latency_ms: number
  p99_latency_ms: number
}

const mockServices: ServiceInfo[] = [
  {
    name: 'safety_service',
    displayName: 'Safety Service',
    status: 'healthy',
    latency_ms: 45,
    last_check: new Date().toISOString(),
    version: '1.2.0',
    endpoints: [
      { path: '/scan', method: 'POST', status: 'ok', latency_ms: 42 },
      { path: '/health', method: 'GET', status: 'ok', latency_ms: 5 },
    ],
    metrics: { requests_24h: 15420, errors_24h: 3, avg_latency_ms: 38, p99_latency_ms: 125 },
  },
  {
    name: 'observer_service',
    displayName: 'Observer Service',
    status: 'healthy',
    latency_ms: 62,
    last_check: new Date().toISOString(),
    version: '1.1.0',
    endpoints: [
      { path: '/analyze', method: 'POST', status: 'ok', latency_ms: 58 },
      { path: '/session', method: 'GET', status: 'ok', latency_ms: 12 },
    ],
    metrics: { requests_24h: 12350, errors_24h: 1, avg_latency_ms: 55, p99_latency_ms: 180 },
  },
  {
    name: 'crisis_engine',
    displayName: 'Crisis Engine',
    status: 'healthy',
    latency_ms: 28,
    last_check: new Date().toISOString(),
    version: '1.3.0',
    endpoints: [
      { path: '/escalate', method: 'POST', status: 'ok', latency_ms: 25 },
      { path: '/status', method: 'GET', status: 'ok', latency_ms: 8 },
    ],
    metrics: { requests_24h: 142, errors_24h: 0, avg_latency_ms: 22, p99_latency_ms: 65 },
  },
  {
    name: 'analytics_service',
    displayName: 'Analytics Service',
    status: 'healthy',
    latency_ms: 85,
    last_check: new Date().toISOString(),
    version: '1.0.5',
    endpoints: [
      { path: '/aggregate', method: 'POST', status: 'ok', latency_ms: 82 },
      { path: '/trends', method: 'GET', status: 'ok', latency_ms: 45 },
    ],
    metrics: { requests_24h: 3240, errors_24h: 0, avg_latency_ms: 78, p99_latency_ms: 220 },
  },
  {
    name: 'audit_service',
    displayName: 'Audit Service',
    status: 'healthy',
    latency_ms: 35,
    last_check: new Date().toISOString(),
    version: '1.1.2',
    endpoints: [
      { path: '/log', method: 'POST', status: 'ok', latency_ms: 32 },
      { path: '/query', method: 'GET', status: 'ok', latency_ms: 18 },
    ],
    metrics: { requests_24h: 45680, errors_24h: 0, avg_latency_ms: 28, p99_latency_ms: 85 },
  },
]

export default function ServiceStatus() {
  const [services, setServices] = useState<ServiceInfo[]>(mockServices)
  const [selectedService, setSelectedService] = useState<ServiceInfo | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      setServices(prev => prev.map(s => ({
        ...s,
        last_check: new Date().toISOString(),
        latency_ms: Math.max(10, (s.latency_ms || 50) + Math.floor(Math.random() * 20 - 10)),
      })))
    }, 5000)
    return () => clearInterval(interval)
  }, [autoRefresh])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-safe text-white'
      case 'degraded': return 'bg-caution text-white'
      case 'down': return 'bg-crisis text-white'
      default: return 'bg-slate-400 text-white'
    }
  }

  const getStatusBg = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-safe-light border-safe'
      case 'degraded': return 'bg-caution-light border-caution'
      case 'down': return 'bg-crisis-light border-crisis'
      default: return 'bg-slate-100 border-slate-300'
    }
  }

  const overallHealth = services.every(s => s.status === 'healthy')
    ? 'All Systems Operational'
    : services.some(s => s.status === 'down')
    ? 'System Outage'
    : 'Degraded Performance'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Service Status</h2>
          <p className="text-sm text-slate-500">Real-time health monitoring of backend services</p>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-slate-300"
            />
            Auto-refresh
          </label>
          <button
            onClick={() => setServices([...services])}
            className="px-4 py-2 text-sm bg-calm-500 text-white rounded-lg hover:bg-calm-600"
          >
            Refresh Now
          </button>
        </div>
      </div>

      {/* Overall Status Banner */}
      <div className={`p-4 rounded-lg border-2 ${
        overallHealth === 'All Systems Operational'
          ? 'bg-safe-light border-safe'
          : overallHealth === 'System Outage'
          ? 'bg-crisis-light border-crisis'
          : 'bg-caution-light border-caution'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${
            overallHealth === 'All Systems Operational' ? 'bg-safe' :
            overallHealth === 'System Outage' ? 'bg-crisis' : 'bg-caution'
          }`} />
          <span className="font-semibold text-slate-800">{overallHealth}</span>
          <span className="text-sm text-slate-500 ml-auto">
            Last updated: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((service) => (
          <div
            key={service.name}
            onClick={() => setSelectedService(service)}
            className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
              selectedService?.name === service.name
                ? 'border-calm-500 bg-calm-50'
                : `${getStatusBg(service.status)} hover:shadow-md`
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-800">{service.displayName}</h3>
              <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(service.status)}`}>
                {service.status}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Latency</span>
                <span className="font-medium text-slate-700">{service.latency_ms}ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Requests (24h)</span>
                <span className="font-medium text-slate-700">{service.metrics.requests_24h.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Errors (24h)</span>
                <span className={`font-medium ${service.metrics.errors_24h > 0 ? 'text-crisis' : 'text-safe'}`}>
                  {service.metrics.errors_24h}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Service Details */}
      {selectedService && (
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-semibold text-slate-800">{selectedService.displayName}</h3>
              <p className="text-sm text-slate-500">Version {selectedService.version}</p>
            </div>
            <span className={`px-3 py-1 rounded-lg text-sm font-medium ${getStatusColor(selectedService.status)}`}>
              {selectedService.status.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Endpoints */}
            <div>
              <h4 className="font-medium text-slate-700 mb-3">Endpoints</h4>
              <div className="space-y-2">
                {selectedService.endpoints.map((ep, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono bg-slate-200 px-2 py-0.5 rounded">
                        {ep.method}
                      </span>
                      <span className="text-sm font-mono text-slate-700">{ep.path}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-500">{ep.latency_ms}ms</span>
                      <span className={`w-2 h-2 rounded-full ${ep.status === 'ok' ? 'bg-safe' : 'bg-crisis'}`} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Metrics */}
            <div>
              <h4 className="font-medium text-slate-700 mb-3">Performance Metrics</h4>
              <div className="grid grid-cols-2 gap-3">
                <MetricBox label="Avg Latency" value={`${selectedService.metrics.avg_latency_ms}ms`} />
                <MetricBox label="P99 Latency" value={`${selectedService.metrics.p99_latency_ms}ms`} />
                <MetricBox label="Requests (24h)" value={selectedService.metrics.requests_24h.toLocaleString()} />
                <MetricBox
                  label="Error Rate"
                  value={`${((selectedService.metrics.errors_24h / selectedService.metrics.requests_24h) * 100).toFixed(3)}%`}
                  status={selectedService.metrics.errors_24h === 0 ? 'good' : 'warning'}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MetricBox({ label, value, status }: { label: string; value: string; status?: 'good' | 'warning' }) {
  return (
    <div className={`p-3 rounded-lg ${status === 'good' ? 'bg-safe-light' : status === 'warning' ? 'bg-caution-light' : 'bg-slate-50'}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-bold text-slate-800">{value}</p>
    </div>
  )
}
