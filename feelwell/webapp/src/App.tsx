import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ChatTester from './pages/ChatTester'
import BenchmarkRunner from './pages/BenchmarkRunner'
import EvaluationResults from './pages/EvaluationResults'
import TestSuites from './pages/TestSuites'
import ServiceStatus from './pages/ServiceStatus'
import PatternEditor from './pages/PatternEditor'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-calm-500 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">FW</span>
                </div>
                <h1 className="text-lg font-semibold text-slate-800">
                  Feelwell Test Console
                </h1>
              </div>
              <nav className="flex gap-1">
                <NavItem to="/">Dashboard</NavItem>
                <NavItem to="/chat">Chat Tester</NavItem>
                <NavItem to="/benchmarks">Benchmarks</NavItem>
                <NavItem to="/results">Benchmark Results</NavItem>
                <NavItem to="/suites">Pipeline Tests</NavItem>
                <NavItem to="/patterns">Patterns</NavItem>
                <NavItem to="/services">Services</NavItem>
              </nav>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<ChatTester />} />
            <Route path="/benchmarks" element={<BenchmarkRunner />} />
            <Route path="/results" element={<EvaluationResults />} />
            <Route path="/suites" element={<TestSuites />} />
            <Route path="/patterns" element={<PatternEditor />} />
            <Route path="/services" element={<ServiceStatus />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive
          ? 'bg-calm-100 text-calm-700'
          : 'text-slate-600 hover:bg-slate-100'
        }`
      }
    >
      {children}
    </NavLink>
  )
}

export default App
