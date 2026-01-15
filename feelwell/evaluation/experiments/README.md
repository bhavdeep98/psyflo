# Feelwell Evaluation Experiments

This directory contains experiment configurations for comprehensive system validation.

## Quick Start

```bash
# Run all evaluations
python -m feelwell.evaluation.cli run --all

# Run specific benchmarks
python -m feelwell.evaluation.cli run --benchmarks

# Run against external datasets
python -m feelwell.evaluation.cli run --datasets mentalchat16k phq9_depression

# Download datasets first
python -m feelwell.evaluation.cli download --dataset all
```

## Experiment Types

### 1. Safety Validation (CRITICAL)
Tests that MUST pass before deployment:
- Crisis detection recall = 100%
- False negative rate = 0%
- All crisis keywords detected

```bash
python -m feelwell.evaluation.cli run --benchmarks
```

### 2. External Benchmark Evaluation
Tests against published clinical datasets:

| Dataset | Source | Purpose |
|---------|--------|---------|
| MentalChat16K | HuggingFace | Conversational counseling |
| PHQ-9 | Kaggle | Depression severity |
| Clinical Decisions | arXiv | Triage reasoning |

```bash
python -m feelwell.evaluation.cli run --datasets mentalchat16k phq9_depression clinical_decisions
```

### 3. Multi-Tier Triage Evaluation
Tests across time horizons:
- **Immediate**: Real-time crisis detection
- **Session**: Within-conversation trajectory
- **Longitudinal**: Cross-session patterns

```bash
python -m feelwell.evaluation.cli run --triage
```

### 4. End-to-End Test Suites
Full pipeline validation:
- **E2E**: Complete message flow
- **Integration**: Service contracts
- **Canary**: Realistic user journeys

```bash
python -m feelwell.evaluation.cli run --suites
```

## Metrics

### Safety Metrics (Non-negotiable)
| Metric | Target | Description |
|--------|--------|-------------|
| Crisis Recall | 100% | All crises detected |
| False Negative Rate | 0% | No missed crises |

### Quality Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Overall Accuracy | >85% | Correct triage level |
| Crisis Precision | >80% | True crisis rate |
| Latency P99 | <100ms | Response time |

### Clinical Alignment
| Metric | Target | Description |
|--------|--------|-------------|
| PHQ-9 Correlation | >0.7 | Score alignment |
| Decision Accuracy | >80% | Correct interventions |

## Running Experiments

### Full Evaluation
```python
from feelwell.evaluation.runner import run_evaluation
from feelwell.services.safety_service.scanner import SafetyScanner

scanner = SafetyScanner()
result = run_evaluation(scanner=scanner)

print(f"Passes Safety: {result.passes_safety_threshold}")
print(f"Crisis Recall: {result.crisis_recall:.2%}")
```

### Category-Specific Evaluation
```python
from feelwell.evaluation.datasets import MentalChat16KLoader

loader = MentalChat16KLoader()
samples = loader.load()

# Get depression-specific samples
depression_samples = loader.get_by_category("depression")

# Get crisis samples
crisis_samples = loader.get_by_triage("crisis")
```

### Fine-tuning Data Preparation
```python
from feelwell.evaluation.datasets import MentalChat16KLoader

loader = MentalChat16KLoader()
train_samples, test_samples = loader.split_train_test()

# Get conversation pairs for training
pairs = loader.get_conversation_pairs()
```

## Results

Results are saved to `feelwell/evaluation/results/`:
- `{run_id}_results.json`: Detailed metrics
- `{run_id}_report.md`: Human-readable report

## Adding New Benchmarks

1. Create JSON file in `feelwell/evaluation/benchmarks/`
2. Follow schema:
```json
{
  "name": "Benchmark Name",
  "description": "Description",
  "version": "1.0.0",
  "cases": [
    {
      "case_id": "CASE-001",
      "category": "crisis_detection",
      "input_text": "Message text",
      "expected_risk_level": "crisis",
      "expected_bypass_llm": true,
      "description": "Case description"
    }
  ]
}
```

## Robustness Testing

For deployment readiness, run adversarial tests:
```bash
python -m feelwell.evaluation.cli run --benchmarks
```

Key adversarial categories:
- Leetspeak substitution (k1ll → kill)
- Unicode evasion (𝕜𝕚𝕝𝕝)
- Teen slang (unalive, sewerslide)
- Coded language (catch the bus)
