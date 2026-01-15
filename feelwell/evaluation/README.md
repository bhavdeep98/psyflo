# Feelwell Evaluation & Test Console

Comprehensive testing platform for validating the Feelwell safety pipeline, crisis detection, and all backend services.

## Quick Start

### 1. Start the API Server
```bash
# Install dependencies
pip install fastapi uvicorn pydantic

# Start API server (port 8000)
python -m feelwell.evaluation.start_console
```

### 2. Start the Webapp
```bash
cd feelwell/webapp
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## CLI Usage

```bash
# Run all evaluations
python -m feelwell.evaluation.cli run --all

# Run specific benchmarks
python -m feelwell.evaluation.cli run --benchmarks

# Run external datasets
python -m feelwell.evaluation.cli run --datasets mentalchat16k phq9_depression

# List available resources
python -m feelwell.evaluation.cli list --benchmarks --datasets
```

## Components

- **benchmarks/**: Internal test cases (crisis detection, adversarial, false positives)
- **datasets/**: External dataset loaders (MentalChat16K, PHQ-9, Clinical Decisions)
- **triage/**: Multi-tier evaluation (immediate, session, longitudinal)
- **suites/**: Test suites (E2E, Integration, Canary)
- **rag/**: RAG evaluation for pattern analysis
- **api/**: REST API for the webapp

## Safety Requirements

Per ADR-001, the system MUST achieve:
- **100% Crisis Recall** - No crisis messages can be missed
- **0 False Negatives** - Every crisis must trigger bypass
