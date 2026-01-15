# Baseline Evaluation Guide

This guide shows you how to run the baseline LLM evaluation with progress tracking.

## Prerequisites

1. **OpenAI API Key** - Required for GPT-4 evaluation
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

2. **Dependencies** - Install if not already installed
   ```bash
   pip install tqdm aiohttp
   ```

## Option 1: Run via Test Console (Recommended)

The test console provides a web UI and API for running evaluations with real-time progress tracking.

### Step 1: Start the Test Console

```bash
cd feelwell
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python -m evaluation.start_console
```

This starts the API server on `http://localhost:8000`

### Step 2: Run Evaluation via CLI

In another terminal:

```bash
cd feelwell
export OPENAI_API_KEY='your-key-here'

# Run baseline evaluation (50 test cases, ~15 minutes)
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python evaluation/cli.py baseline --test-cases 50

# Or with 100 test cases (~30 minutes)
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python evaluation/cli.py baseline --test-cases 100

# Or full evaluation with 200 test cases (~60 minutes)
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python evaluation/cli.py baseline --test-cases 200
```

You'll see real-time progress like this:

```
============================================================
Feelwell Baseline Evaluation (via Test Console)
============================================================
API URL: http://localhost:8000
Model: feelwell-baseline
Test Cases: 50
Estimated Time: ~15 minutes
============================================================

🚀 Starting evaluation...
✅ Evaluation started: baseline_a3f2c8d1

 45.2% ████████████████████░░░░░░░░░░░░░░░░░░░░ running_evaluation (23/50 cases) Score: 7.1/10
```

### Step 3: View Results in Web UI (Optional)

1. Start the webapp:
   ```bash
   cd feelwell/webapp
   npm install
   npm run dev
   ```

2. Open `http://localhost:5173` in your browser

3. Navigate to "Evaluation Results" to see detailed metrics

## Option 2: Run Standalone Script

If you don't want to use the test console, you can run the standalone script:

```bash
cd feelwell
export OPENAI_API_KEY='your-key-here'

# Run with progress bar
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python scripts/run_baseline_eval.py \
  --test-cases 50 \
  --model-name feelwell-baseline \
  --output-dir evaluation_results

# Run without progress bar
PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH \
  ../.venv/bin/python scripts/run_baseline_eval.py \
  --test-cases 50 \
  --no-progress
```

## Understanding the Results

### Key Metrics

- **Overall Score**: Average across all 7 clinical metrics (target: ≥7.5/10)
- **Pass Rate**: Percentage of responses meeting minimum thresholds (target: ≥75%)

### 7 Clinical Metrics (from MentalChat16K paper)

1. **Active Listening** (7.2/10 baseline) - Reflects understanding, captures essence
2. **Empathy & Validation** (7.5/10 baseline) - Validates feelings, shows compassion
3. **Safety & Trustworthiness** (8.1/10 baseline) - Prioritizes safety, accurate info
4. **Open-mindedness** (6.9/10 baseline) - Bias-free, respectful
5. **Clarity & Encouragement** (6.5/10 baseline) - Clear, motivating responses
6. **Boundaries & Ethical** (7.0/10 baseline) - Clarifies role, recommends help
7. **Holistic Approach** (6.3/10 baseline) - Addresses emotional, cognitive, situational

### Expected Baseline Results

Based on the simple empathetic response template:

```
Overall Score: ~6.8/10
Pass Rate: ~45%
```

### Target with Pre-trained Model

After deploying Mental-Health-FineTuned-Mistral-7B:

```
Overall Score: 7.8-8.0/10 (+15-18% improvement)
Pass Rate: 75-85% (+67-89% improvement)
```

## Output Files

Results are saved to:
- **Standalone**: `feelwell/evaluation_results/feelwell-baseline_YYYYMMDD_HHMMSS.json`
- **Test Console**: `feelwell/evaluation/results/baseline_RUNID_YYYYMMDD_HHMMSS.json`

## Troubleshooting

### "Module not found" errors

Make sure PYTHONPATH is set correctly:
```bash
export PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH
```

### "OpenAI API key required"

Export your API key:
```bash
export OPENAI_API_KEY='sk-...'
```

### Test console not starting

Install FastAPI and uvicorn:
```bash
pip install fastapi uvicorn
```

### Slow evaluation

- Start with 50 test cases (~15 minutes)
- Each test case takes ~18 seconds (GPT-4 evaluation)
- 200 test cases will take ~60 minutes

### Rate limit errors

If you hit OpenAI rate limits:
- Reduce concurrent evaluations in the code
- Wait a few minutes and retry
- Use a higher-tier API key

## Next Steps

After running the baseline evaluation:

1. **Review Results** - Check if baseline meets minimum thresholds
2. **Deploy Pre-trained Model** - Week 2 of execution plan
3. **Run Comparative Evaluation** - Compare baseline vs new model
4. **A/B Testing** - Gradual production rollout

See `docs/EXECUTION_PLAN.md` for the complete 4-week roadmap.

## Cost Estimate

- **50 test cases**: ~$2 (GPT-4 API calls)
- **100 test cases**: ~$4
- **200 test cases**: ~$7

Total for Phase 2 (baseline + model evaluation): ~$20
