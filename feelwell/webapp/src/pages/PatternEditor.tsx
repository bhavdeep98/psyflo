import { useState, useEffect } from 'react'

interface Pattern {
  id: string
  pattern: string
  category: 'crisis' | 'caution' | 'semantic'
  framework?: string
  item?: number
  severity?: number
  description: string
  examples: string[]
  testResults?: {
    matches: number
    falsePositives: number
    falseNegatives: number
  }
}

interface TestResult {
  input: string
  matched: boolean
  matchedPattern?: string
  expectedMatch: boolean
}

// Current patterns from the codebase
const CRISIS_PATTERNS: Pattern[] = [
  { id: 'c1', pattern: 'kill myself', category: 'crisis', description: 'Direct self-harm', examples: ['I want to kill myself'] },
  { id: 'c2', pattern: 'end my life', category: 'crisis', description: 'Direct self-harm', examples: ['I want to end my life'] },
  { id: 'c3', pattern: 'want to die', category: 'crisis', description: 'Direct self-harm', examples: ['I just want to die'] },
  { id: 'c4', pattern: 'suicide', category: 'crisis', description: 'Direct mention', examples: ['thinking about suicide'] },
  { id: 'c5', pattern: 'never wake up', category: 'crisis', description: 'Passive suicidal ideation', examples: ['go to sleep and never wake up'] },
  { id: 'c6', pattern: 'sleep forever', category: 'crisis', description: 'Passive suicidal ideation', examples: ['I just want to sleep forever'] },
  { id: 'c7', pattern: 'disappear forever', category: 'crisis', description: 'Passive suicidal ideation', examples: ['I wish I could disappear forever'] },
  { id: 'c8', pattern: 'unalive', category: 'crisis', description: 'Teen coded language', examples: ['I want to unalive myself'] },
  { id: 'c9', pattern: 'kms', category: 'crisis', description: 'Abbreviation', examples: ['honestly kms'] },
  { id: 'c10', pattern: 'better off without me', category: 'crisis', description: 'Burden ideation', examples: ['everyone would be better off without me'] },
]

const CAUTION_PATTERNS: Pattern[] = [
  { id: 'ca1', pattern: 'hopeless', category: 'caution', description: 'PHQ-9 Item 2', examples: ['I feel hopeless'] },
  { id: 'ca2', pattern: 'worthless', category: 'caution', description: 'PHQ-9 Item 6', examples: ['I feel worthless'] },
  { id: 'ca3', pattern: 'burden', category: 'caution', description: 'Burden ideation', examples: ["I'm a burden to everyone"] },
  { id: 'ca4', pattern: 'nobody cares', category: 'caution', description: 'Isolation', examples: ['nobody cares about me'] },
  { id: 'ca5', pattern: 'alone', category: 'caution', description: 'Isolation', examples: ['I feel so alone'] },
  { id: 'ca6', pattern: "can't go on", category: 'caution', description: 'Exhaustion', examples: ["I can't go on like this"] },
  { id: 'ca7', pattern: 'hate myself', category: 'caution', description: 'Self-loathing', examples: ['I hate myself'] },
  { id: 'ca8', pattern: 'trapped', category: 'caution', description: 'Hopelessness', examples: ['I feel trapped'] },
]

const SEMANTIC_PATTERNS: Pattern[] = [
  { id: 's1', pattern: "don't want to wake up", category: 'semantic', framework: 'PHQ9', item: 9, severity: 3, description: 'Passive SI', examples: ["I don't want to wake up tomorrow"] },
  { id: 's2', pattern: 'go to sleep and never', category: 'semantic', framework: 'PHQ9', item: 9, severity: 3, description: 'Passive SI', examples: ['go to sleep and never wake up'] },
  { id: 's3', pattern: 'no reason to keep going', category: 'semantic', framework: 'PHQ9', item: 9, severity: 3, description: 'Hopelessness', examples: ['there is no reason to keep going'] },
  { id: 's4', pattern: 'nothing makes me happy', category: 'semantic', framework: 'PHQ9', item: 1, severity: 3, description: 'Anhedonia', examples: ['nothing makes me happy anymore'] },
  { id: 's5', pattern: "can't enjoy", category: 'semantic', framework: 'PHQ9', item: 1, severity: 2, description: 'Anhedonia', examples: ["I can't enjoy anything"] },
  { id: 's6', pattern: "can't stop worrying", category: 'semantic', framework: 'GAD7', item: 2, severity: 3, description: 'Uncontrollable worry', examples: ["I can't stop worrying about everything"] },
]

export default function PatternEditor() {
  const [activeTab, setActiveTab] = useState<'crisis' | 'caution' | 'semantic'>('crisis')
  const [patterns, setPatterns] = useState<Pattern[]>([])
  const [testInput, setTestInput] = useState('')
  const [testResults, setTestResults] = useState<TestResult[]>([])


  useEffect(() => {
    // Load patterns based on active tab
    switch (activeTab) {
      case 'crisis':
        setPatterns(CRISIS_PATTERNS)
        break
      case 'caution':
        setPatterns(CAUTION_PATTERNS)
        break
      case 'semantic':
        setPatterns(SEMANTIC_PATTERNS)
        break
    }
  }, [activeTab])

  const testPattern = async () => {
    if (!testInput.trim()) return

    const results: TestResult[] = []
    const normalizedInput = testInput.toLowerCase()

    // Test against all patterns in current category
    let matched = false
    let matchedPattern = ''

    for (const pattern of patterns) {
      if (normalizedInput.includes(pattern.pattern.toLowerCase())) {
        matched = true
        matchedPattern = pattern.pattern
        break
      }
    }

    results.push({
      input: testInput,
      matched,
      matchedPattern: matched ? matchedPattern : undefined,
      expectedMatch: true, // User is testing, so they expect a match
    })

    setTestResults(results)

    // Also test against the real API
    try {
      const response = await fetch('http://localhost:8000/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: testInput, student_id: 'pattern_test' }),
      })
      if (response.ok) {
        const data = await response.json()
        results.push({
          input: `API Result: ${data.risk_level}`,
          matched: data.risk_level !== 'safe',
          matchedPattern: data.matched_keywords?.join(', ') || 'semantic',
          expectedMatch: true,
        })
        setTestResults([...results])
      }
    } catch {
      // API not available
    }
  }

  const copyPatternCode = (pattern: Pattern) => {
    let code = ''
    if (pattern.category === 'crisis' || pattern.category === 'caution') {
      code = `"${pattern.pattern}",`
    } else {
      code = `(r"\\b${pattern.pattern.replace(/'/g, "\\'")}\\b", ${pattern.severity || 2}),`
    }
    navigator.clipboard.writeText(code)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Pattern Editor</h2>
          <p className="text-sm text-slate-500">
            View and test safety detection patterns. Edit in <code className="bg-slate-100 px-1 rounded">config.py</code> and <code className="bg-slate-100 px-1 rounded">semantic_analyzer.py</code>
          </p>
        </div>
      </div>

      {/* Pattern Tester */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="font-semibold text-slate-800 mb-3">🧪 Pattern Tester</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && testPattern()}
            placeholder="Enter a message to test against patterns..."
            className="flex-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-calm-500"
          />
          <button
            onClick={testPattern}
            className="px-4 py-2 bg-calm-500 text-white rounded-lg hover:bg-calm-600"
          >
            Test
          </button>
        </div>
        {testResults.length > 0 && (
          <div className="mt-3 space-y-2">
            {testResults.map((result, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg ${result.matched ? 'bg-crisis-light border border-crisis/30' : 'bg-safe-light border border-safe/30'
                  }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {result.matched ? '🚨 MATCHED' : '✅ NO MATCH'}
                  </span>
                  {result.matchedPattern && (
                    <span className="text-xs bg-white/50 px-2 py-0.5 rounded">
                      Pattern: "{result.matchedPattern}"
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-600 mt-1">{result.input}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        {(['crisis', 'caution', 'semantic'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === tab
                ? tab === 'crisis' ? 'border-crisis text-crisis-dark' :
                  tab === 'caution' ? 'border-caution text-caution-dark' :
                    'border-calm-500 text-calm-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            {tab === 'crisis' ? '🚨 Crisis Keywords' :
              tab === 'caution' ? '⚠️ Caution Keywords' :
                '🧠 Semantic Patterns'}
            <span className="ml-2 text-xs bg-slate-100 px-1.5 py-0.5 rounded">
              {tab === 'crisis' ? CRISIS_PATTERNS.length :
                tab === 'caution' ? CAUTION_PATTERNS.length :
                  SEMANTIC_PATTERNS.length}
            </span>
          </button>
        ))}
      </div>

      {/* File Location */}
      <div className="bg-slate-50 rounded-lg p-3 text-sm">
        <span className="font-medium text-slate-700">📁 File: </span>
        <code className="text-slate-600">
          {activeTab === 'semantic'
            ? 'feelwell/services/safety_service/semantic_analyzer.py'
            : 'feelwell/services/safety_service/config.py'}
        </code>
        <span className="text-slate-500 ml-2">
          ({activeTab === 'crisis' ? 'CRISIS_KEYWORDS' :
            activeTab === 'caution' ? 'CAUTION_KEYWORDS' :
              'PHQ9_PATTERNS / GAD7_PATTERNS'})
        </span>
      </div>

      {/* Patterns List */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-slate-600">Pattern</th>
              {activeTab === 'semantic' && (
                <>
                  <th className="text-left py-3 px-4 font-medium text-slate-600">Framework</th>
                  <th className="text-center py-3 px-4 font-medium text-slate-600">Item</th>
                  <th className="text-center py-3 px-4 font-medium text-slate-600">Severity</th>
                </>
              )}
              <th className="text-left py-3 px-4 font-medium text-slate-600">Description</th>
              <th className="text-left py-3 px-4 font-medium text-slate-600">Example</th>
              <th className="text-center py-3 px-4 font-medium text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody>
            {patterns.map((pattern) => (
              <tr key={pattern.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="py-3 px-4">
                  <code className={`px-2 py-0.5 rounded text-xs ${pattern.category === 'crisis' ? 'bg-crisis-light text-crisis-dark' :
                      pattern.category === 'caution' ? 'bg-caution-light text-caution-dark' :
                        'bg-calm-100 text-calm-700'
                    }`}>
                    {pattern.pattern}
                  </code>
                </td>
                {activeTab === 'semantic' && (
                  <>
                    <td className="py-3 px-4 text-slate-600">{pattern.framework}</td>
                    <td className="py-3 px-4 text-center text-slate-600">{pattern.item}</td>
                    <td className="py-3 px-4 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs ${pattern.severity === 3 ? 'bg-crisis-light text-crisis-dark' :
                          pattern.severity === 2 ? 'bg-caution-light text-caution-dark' :
                            'bg-slate-100 text-slate-600'
                        }`}>
                        {pattern.severity}
                      </span>
                    </td>
                  </>
                )}
                <td className="py-3 px-4 text-slate-600">{pattern.description}</td>
                <td className="py-3 px-4 text-slate-500 text-xs italic">
                  "{pattern.examples[0]}"
                </td>
                <td className="py-3 px-4 text-center">
                  <button
                    onClick={() => copyPatternCode(pattern)}
                    className="text-xs text-calm-600 hover:text-calm-700"
                    title="Copy code"
                  >
                    📋 Copy
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Pattern Suggestion */}
      <div className="bg-slate-50 rounded-lg p-4">
        <h4 className="font-medium text-slate-700 mb-2">💡 Adding New Patterns</h4>
        <p className="text-sm text-slate-600 mb-3">
          To add a new pattern, edit the appropriate file and restart the backend:
        </p>
        <div className="bg-white rounded-lg p-3 font-mono text-xs overflow-x-auto">
          {activeTab === 'crisis' && (
            <pre className="text-slate-700">{`# In config.py, add to CRISIS_KEYWORDS:
CRISIS_KEYWORDS: FrozenSet[str] = frozenset({
    ...
    "your new pattern here",
})`}</pre>
          )}
          {activeTab === 'caution' && (
            <pre className="text-slate-700">{`# In config.py, add to CAUTION_KEYWORDS:
CAUTION_KEYWORDS: FrozenSet[str] = frozenset({
    ...
    "your new pattern here",
})`}</pre>
          )}
          {activeTab === 'semantic' && (
            <pre className="text-slate-700">{`# In semantic_analyzer.py, add to PHQ9_PATTERNS[item_number]:
PHQ9_PATTERNS: Dict[int, Dict] = {
    9: {  # Suicidal ideation
        "patterns": [
            ...
            (r"\\byour pattern here\\b", 3),  # severity 1-3
        ],
    },
}`}</pre>
          )}
        </div>
      </div>
    </div>
  )
}
