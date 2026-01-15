#!/bin/bash
# Quick script to check evaluation progress

echo "Checking baseline evaluation progress..."
echo ""

# Check if process is running
if pgrep -f "run_baseline_eval.py" > /dev/null; then
    echo "✅ Evaluation is running"
    echo ""
    
    # Show recent output if results file exists
    if [ -d "evaluation_results" ]; then
        echo "📁 Results directory exists"
        ls -lh evaluation_results/ 2>/dev/null || echo "No results yet"
    fi
    
    echo ""
    echo "The evaluation is processing 50 test cases."
    echo "Each case takes ~18 seconds (GPT-4 evaluation)."
    echo "Total estimated time: ~15 minutes"
    echo ""
    echo "You can monitor the terminal where you started the evaluation"
    echo "to see the progress bar updating in real-time."
    
else
    echo "⚠️  Evaluation process not found"
    echo ""
    echo "Check if it completed or failed:"
    echo "  - Look for results in evaluation_results/"
    echo "  - Check the terminal where you started it"
fi
