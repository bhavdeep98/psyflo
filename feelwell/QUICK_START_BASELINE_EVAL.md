# Quick Start: Baseline Evaluation

Run the baseline LLM evaluation in 3 easy steps!

## Prerequisites

```bash
export OPENAI_API_KEY='your-key-here'
```

## Method 1: One-Command Run (Easiest)

```bash
cd feelwell
./run_baseline_eval.sh 50
```

This will:
1. Check if test console is running
2. If yes: Run evaluation via console with progress tracking
3. If no: Offer to run standalone script

## Method 2: Via Test Console (Recommended)

### Terminal 1: Start Test Console

```bash
cd feelwell
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python -m evaluation.start_console
```

### Terminal 2: Run Evaluation

```bash
cd feelwell
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python evaluation/cli.py baseline --test-cases 50
```

**Progress tracking:**
```
 45.2% ████████████████████░░░░░░░░░░░░░░░░░░░░ running_evaluation (23/50 cases) Score: 7.1/10
```

## Method 3: Standalone Script

```bash
cd feelwell
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python scripts/run_baseline_eval.py --test-cases 50
```

## Test Case Options

- `--test-cases 50` - Quick evaluation (~15 minutes, ~$2)
- `--test-cases 100` - Medium evaluation (~30 minutes, ~$4)
- `--test-cases 200` - Full evaluation (~60 minutes, ~$7)

## What You'll See

```
============================================================
Feelwell Baseline Evaluation
============================================================
Model: feelwell-baseline
Test Cases: 50
Estimated Time: ~15 minutes
============================================================

Evaluating: 100%|████████████████████| 50/50 [15:23<00:00, 18.5s/case]

✅ Evaluation completed successfully!

📊 Key Metrics:
  Overall Score: 6.82/10
  Pass Rate: 44.0%

📈 Metric Breakdown:
  Active Listening: 7.20/10
  Empathy & Validation: 7.50/10
  Safety & Trustworthiness: 8.10/10
  Open-mindedness: 6.90/10
  Clarity & Encouragement: 6.50/10
  Boundaries & Ethical: 7.00/10
  Holistic Approach: 6.30/10

⚠️  Below minimum quality threshold (7.5/10) - Gap: 0.68 points

📁 Results saved to: evaluation_results/feelwell-baseline_20260115_143022.json
```

## Next Steps

1. ✅ **Baseline established** - You now have performance metrics
2. 🚀 **Deploy pre-trained model** - Mental-Health-FineTuned-Mistral-7B
3. 📊 **Run comparative evaluation** - Compare baseline vs new model
4. 🎯 **A/B testing** - Gradual production rollout

See `docs/EXECUTION_PLAN.md` for the complete roadmap.

## Troubleshooting

**"Module not found"**
```bash
export PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH
```

**"OpenAI API key required"**
```bash
export OPENAI_API_KEY='sk-...'
```

**Test console not starting**
```bash
pip install fastapi uvicorn aiohttp tqdm
```

## Files Created

- `evaluation_results/` - Evaluation results (JSON)
- `evaluation/results/` - Test console results
- Logs in CloudWatch (production) or console (development)

## Cost

- 50 cases: ~$2
- 100 cases: ~$4  
- 200 cases: ~$7

All costs are for GPT-4 API calls used in evaluation.
