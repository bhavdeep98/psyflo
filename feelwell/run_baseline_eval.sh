#!/bin/bash
# Quick script to run baseline evaluation through the test console

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  Feelwell Baseline Evaluation${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ Error: OPENAI_API_KEY environment variable is not set${NC}"
    echo ""
    echo "Please export your OpenAI API key:"
    echo "  export OPENAI_API_KEY='your-key-here'"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ OpenAI API key found${NC}"

# Set PYTHONPATH
export PYTHONPATH="/Users/bhavdeepsinghsachdeva/Psyflo:$PYTHONPATH"

# Parse arguments
TEST_CASES=${1:-50}
MODEL_NAME=${2:-feelwell-baseline}

echo -e "${BLUE}Configuration:${NC}"
echo "  Test Cases: $TEST_CASES"
echo "  Model Name: $MODEL_NAME"
echo "  Estimated Time: ~$((TEST_CASES * 18 / 60)) minutes"
echo ""

# Check if test console is running
echo -e "${YELLOW}Checking if test console is running...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Test console is running${NC}"
    echo ""
    
    # Run via CLI
    echo -e "${BLUE}Starting evaluation via test console...${NC}"
    echo ""
    ../.venv/bin/python evaluation/cli.py baseline \
        --test-cases "$TEST_CASES" \
        --model-name "$MODEL_NAME"
    
else
    echo -e "${YELLOW}⚠️  Test console is not running${NC}"
    echo ""
    echo "You have two options:"
    echo ""
    echo -e "${BLUE}Option 1: Start test console (recommended)${NC}"
    echo "  In one terminal:"
    echo "    cd feelwell"
    echo "    PYTHONPATH=/Users/bhavdeepsinghsachdeva/Psyflo:\$PYTHONPATH \\"
    echo "      ../.venv/bin/python -m evaluation.start_console"
    echo ""
    echo "  Then in another terminal, run this script again:"
    echo "    ./run_baseline_eval.sh $TEST_CASES"
    echo ""
    echo -e "${BLUE}Option 2: Run standalone script${NC}"
    echo "    ../.venv/bin/python scripts/run_baseline_eval.py \\"
    echo "      --test-cases $TEST_CASES \\"
    echo "      --model-name $MODEL_NAME"
    echo ""
    
    # Ask user if they want to run standalone
    read -p "Run standalone script now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}Running standalone evaluation...${NC}"
        echo ""
        ../.venv/bin/python scripts/run_baseline_eval.py \
            --test-cases "$TEST_CASES" \
            --model-name "$MODEL_NAME" \
            --output-dir evaluation_results
    fi
fi
