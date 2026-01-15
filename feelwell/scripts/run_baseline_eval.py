#!/usr/bin/env python3
"""Run baseline evaluation on current Feelwell system.

This script evaluates the current system's responses against the
MentalChat16K clinical metrics to establish a baseline before
integrating new LLM models.

Usage:
    python scripts/run_baseline_eval.py --api-key YOUR_GPT4_KEY
    
    # Or use environment variable
    export OPENAI_API_KEY=your-key
    python scripts/run_baseline_eval.py
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.suites.mentalchat_eval import run_baseline_evaluation

# Try to import tqdm for progress bar
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("Note: Install 'tqdm' for progress bars: pip install tqdm")


async def generate_baseline_response(question: str) -> str:
    """Generate response using current Feelwell system.
    
    This is a placeholder that should be replaced with actual
    integration to your current response generation system.
    
    Args:
        question: Student's question
        
    Returns:
        Generated response
    """
    # TODO: Replace with actual Feelwell response generation
    # For now, return a simple empathetic response
    return f"""I hear you, and I want you to know that what you're feeling is valid. 
It takes courage to reach out and share what you're going through.

I'd encourage you to speak with your school counselor about this. They're trained 
to help with situations like yours and they care about your wellbeing.

If you need immediate support, you can also reach out to:
• Crisis Text Line: Text HOME to 741741 (24/7)
• National Suicide Prevention Lifeline: 988

Remember, you don't have to go through this alone. There are people who want to help."""


class ProgressCallback:
    """Callback for tracking evaluation progress."""
    
    def __init__(self, total: int, use_tqdm: bool = True):
        self.total = total
        self.completed = 0
        self.use_tqdm = use_tqdm and TQDM_AVAILABLE
        self.pbar = None
        
        if self.use_tqdm:
            self.pbar = tqdm(total=total, desc="Evaluating", unit="case")
    
    def update(self, increment: int = 1):
        """Update progress."""
        self.completed += increment
        if self.pbar:
            self.pbar.update(increment)
        else:
            # Simple text progress
            percent = (self.completed / self.total) * 100
            print(f"\rProgress: {self.completed}/{self.total} ({percent:.1f}%)", end="", flush=True)
    
    def close(self):
        """Close progress bar."""
        if self.pbar:
            self.pbar.close()
        else:
            print()  # New line after progress


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run baseline evaluation on Feelwell system"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY"),
        help="OpenAI API key for GPT-4 evaluation (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--model-name",
        default="feelwell-baseline",
        help="Name for this evaluation run"
    )
    parser.add_argument(
        "--output-dir",
        default="./evaluation_results",
        help="Directory to save results"
    )
    parser.add_argument(
        "--test-cases",
        type=int,
        default=50,
        choices=[50, 100, 200],
        help="Number of test cases to evaluate (50, 100, or 200)"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar"
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: OpenAI API key required")
        print("\nProvide via --api-key argument or OPENAI_API_KEY environment variable:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python scripts/run_baseline_eval.py")
        return 1
    
    print("\n" + "="*60)
    print("Feelwell Baseline Evaluation")
    print("="*60)
    print(f"Model: {args.model_name}")
    print(f"Test Cases: {args.test_cases}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Estimated Time: ~{args.test_cases * 0.3:.0f} minutes")
    print("="*60 + "\n")
    
    # Create progress callback
    progress = ProgressCallback(args.test_cases, use_tqdm=not args.no_progress)
    
    # Run evaluation
    try:
        result = await run_baseline_evaluation(
            gpt4_api_key=args.api_key,
            model_generate_fn=generate_baseline_response,
            model_name=args.model_name,
            output_dir=args.output_dir,
            progress_callback=progress.update
        )
        
        progress.close()
        
        print("\n✅ Evaluation completed successfully!")
        print(f"\n📊 Key Metrics:")
        print(f"  Overall Score: {result.summary.get('overall_average', 0):.2f}/10")
        print(f"  Pass Rate: {result.pass_rate:.1f}%")
        print(f"\n📈 Metric Breakdown:")
        print(f"  Active Listening: {result.summary.get('active_listening_avg', 0):.2f}/10")
        print(f"  Empathy & Validation: {result.summary.get('empathy_validation_avg', 0):.2f}/10")
        print(f"  Safety & Trustworthiness: {result.summary.get('safety_trustworthiness_avg', 0):.2f}/10")
        print(f"  Open-mindedness: {result.summary.get('open_mindedness_avg', 0):.2f}/10")
        print(f"  Clarity & Encouragement: {result.summary.get('clarity_encouragement_avg', 0):.2f}/10")
        print(f"  Boundaries & Ethical: {result.summary.get('boundaries_ethical_avg', 0):.2f}/10")
        print(f"  Holistic Approach: {result.summary.get('holistic_approach_avg', 0):.2f}/10")
        
        # Check if meets thresholds
        overall_avg = result.summary.get('overall_average', 0)
        if overall_avg >= 7.5:
            print("\n✅ Meets minimum quality threshold (7.5/10)")
        else:
            print(f"\n⚠️  Below minimum quality threshold (7.5/10) - Gap: {7.5 - overall_avg:.2f} points")
        
        print(f"\n📁 Results saved to: {result.output_file}")
        
        return 0
        
    except Exception as e:
        progress.close()
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
