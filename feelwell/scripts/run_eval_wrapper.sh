#!/bin/bash
# Wrapper script to run baseline evaluation with proper environment setup

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY environment variable is not set"
    echo ""
    echo "Please export your OpenAI API key:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    exit 1
fi

# Set PYTHONPATH to include parent directory
export PYTHONPATH="/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH"

# Run the evaluation
cd "$(dirname "$0")/.."
../.venv/bin/python scripts/run_baseline_eval.py \
    --api-key "$OPENAI_API_KEY" \
    --model-name feelwell-baseline \
    --test-cases 50 \
    --output-dir evaluation_results

echo ""
echo "✅ Evaluation complete! Check evaluation_results/ for results."
