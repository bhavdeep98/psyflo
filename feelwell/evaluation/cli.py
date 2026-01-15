#!/usr/bin/env python3
"""CLI for running evaluations through the Feelwell Test Console.

This provides a command-line interface to trigger evaluations
and monitor their progress through the API.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("Error: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)


class EvaluationCLI:
    """CLI for running evaluations."""
    
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
    
    async def run_baseline_eval(
        self,
        test_cases: int = 50,
        model_name: str = "feelwell-baseline",
        api_key: str = None
    ):
        """Run baseline LLM evaluation."""
        
        # Get API key
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            print("❌ Error: OpenAI API key required")
            print("\nProvide via --api-key argument or OPENAI_API_KEY environment variable:")
            print("  export OPENAI_API_KEY='your-key-here'")
            return 1
        
        print("\n" + "="*60)
        print("Feelwell Baseline Evaluation (via Test Console)")
        print("="*60)
        print(f"API URL: {self.api_url}")
        print(f"Model: {model_name}")
        print(f"Test Cases: {test_cases}")
        print(f"Estimated Time: ~{test_cases * 0.3:.0f} minutes")
        print("="*60 + "\n")
        
        async with aiohttp.ClientSession() as session:
            # Start evaluation
            print("🚀 Starting evaluation...")
            async with session.post(
                f"{self.api_url}/api/llm/baseline-eval",
                json={
                    "test_cases": test_cases,
                    "model_name": model_name,
                    "api_key": api_key
                }
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ Failed to start evaluation: {error}")
                    return 1
                
                data = await resp.json()
                run_id = data["run_id"]
                print(f"✅ Evaluation started: {run_id}\n")
            
            # Poll for progress
            last_progress = 0
            last_step = ""
            
            while True:
                await asyncio.sleep(2)  # Poll every 2 seconds
                
                async with session.get(
                    f"{self.api_url}/api/llm/baseline-eval/{run_id}"
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ Failed to get status")
                        return 1
                    
                    status = await resp.json()
                    
                    # Update progress
                    progress = status["progress"]
                    current_step = status.get("current_step", "")
                    
                    if progress != last_progress or current_step != last_step:
                        self._print_progress(progress, current_step, status.get("metrics", {}))
                        last_progress = progress
                        last_step = current_step
                    
                    # Check if completed
                    if status["status"] == "completed":
                        print("\n✅ Evaluation completed successfully!\n")
                        self._print_results(status["results"])
                        return 0
                    
                    elif status["status"] == "error":
                        print(f"\n❌ Evaluation failed: {status.get('error')}")
                        return 1
    
    def _print_progress(self, progress: float, step: str, metrics: dict):
        """Print progress bar."""
        bar_length = 40
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        percent = progress * 100
        
        # Build status line
        status_parts = [f"{percent:5.1f}%", bar, step]
        
        if metrics.get("completed_cases"):
            status_parts.append(
                f"({metrics['completed_cases']}/{metrics.get('total_cases', '?')} cases)"
            )
        
        if metrics.get("current_average_score"):
            status_parts.append(f"Score: {metrics['current_average_score']:.2f}/10")
        
        print(f"\r{' '.join(status_parts)}", end="", flush=True)
    
    def _print_results(self, results: dict):
        """Print final results."""
        print("📊 Final Results:")
        print(f"  Overall Score: {results['overall_score']:.2f}/10")
        print(f"  Pass Rate: {results['pass_rate']:.1f}%")
        print(f"  Total Cases: {results['total_cases']}")
        
        print(f"\n📈 Metric Breakdown:")
        for metric, score in results.get("metric_scores", {}).items():
            metric_name = metric.replace("_", " ").title()
            print(f"  {metric_name}: {score:.2f}/10")
        
        print(f"\n📁 Results saved to: {results.get('output_file', 'N/A')}")
        
        # Check threshold
        if results['overall_score'] >= 7.5:
            print("\n✅ Meets minimum quality threshold (7.5/10)")
        else:
            gap = 7.5 - results['overall_score']
            print(f"\n⚠️  Below minimum quality threshold (7.5/10) - Gap: {gap:.2f} points")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Feelwell Evaluation CLI"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Test Console API URL"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Baseline evaluation command
    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Run baseline LLM evaluation"
    )
    baseline_parser.add_argument(
        "--test-cases",
        type=int,
        default=50,
        choices=[50, 100, 200],
        help="Number of test cases (50, 100, or 200)"
    )
    baseline_parser.add_argument(
        "--model-name",
        default="feelwell-baseline",
        help="Name for this evaluation run"
    )
    baseline_parser.add_argument(
        "--api-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = EvaluationCLI(api_url=args.api_url)
    
    if args.command == "baseline":
        return await cli.run_baseline_eval(
            test_cases=args.test_cases,
            model_name=args.model_name,
            api_key=args.api_key
        )
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
