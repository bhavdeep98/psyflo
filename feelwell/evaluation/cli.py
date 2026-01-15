#!/usr/bin/env python3
"""Command-line interface for running evaluations.

Usage:
    python -m feelwell.evaluation.cli --help
    python -m feelwell.evaluation.cli run --all
    python -m feelwell.evaluation.cli run --benchmarks --datasets mentalchat16k phq9
    python -m feelwell.evaluation.cli download --dataset mentalchat16k
    python -m feelwell.evaluation.cli report --run-id eval_abc123
"""
import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_parser() -> argparse.ArgumentParser:
    """Set up argument parser."""
    parser = argparse.ArgumentParser(
        description="Feelwell Evaluation Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run evaluation")
    run_parser.add_argument(
        "--all", action="store_true",
        help="Run all evaluations"
    )
    run_parser.add_argument(
        "--benchmarks", action="store_true",
        help="Run internal benchmarks"
    )
    run_parser.add_argument(
        "--datasets", nargs="+",
        choices=["mentalchat16k", "phq9_depression", "clinical_decisions"],
        help="External datasets to evaluate"
    )
    run_parser.add_argument(
        "--triage", action="store_true",
        help="Run triage evaluation"
    )
    run_parser.add_argument(
        "--suites", action="store_true",
        help="Run test suites (E2E, Integration, Canary)"
    )
    run_parser.add_argument(
        "--max-samples", type=int,
        help="Maximum samples per dataset"
    )
    run_parser.add_argument(
        "--output-dir", type=str,
        default="feelwell/evaluation/results",
        help="Output directory for results"
    )
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download datasets")
    download_parser.add_argument(
        "--dataset", required=True,
        choices=["mentalchat16k", "phq9_depression", "clinical_decisions", "all"],
        help="Dataset to download"
    )
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument(
        "--run-id", required=True,
        help="Run ID to generate report for"
    )
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available resources")
    list_parser.add_argument(
        "--datasets", action="store_true",
        help="List available datasets"
    )
    list_parser.add_argument(
        "--benchmarks", action="store_true",
        help="List available benchmarks"
    )
    list_parser.add_argument(
        "--results", action="store_true",
        help="List previous evaluation results"
    )
    
    return parser


def cmd_run(args) -> int:
    """Run evaluation command."""
    from .runner import EvaluationRunner, EvaluationConfig
    
    # Build config
    config = EvaluationConfig(
        run_internal_benchmarks=args.all or args.benchmarks,
        run_external_datasets=args.all or bool(args.datasets),
        run_triage_evaluation=args.all or args.triage,
        run_test_suites=args.all or args.suites,
        output_dir=Path(args.output_dir),
    )
    
    if args.datasets:
        config.datasets_to_include = args.datasets
    
    if args.max_samples:
        config.max_samples_per_dataset = args.max_samples
    
    # Initialize scanner if available
    scanner = None
    try:
        from feelwell.services.safety_service.scanner import SafetyScanner
        from feelwell.shared.utils import configure_pii_salt
        configure_pii_salt("evaluation_salt_32_characters_long!")
        scanner = SafetyScanner()
        logger.info("SafetyScanner initialized")
    except ImportError:
        logger.warning("SafetyScanner not available, running with mocks")
    
    # Run evaluation
    runner = EvaluationRunner(config=config, scanner=scanner)
    result = runner.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    print(f"Run ID: {result.run_id}")
    print(f"Total Samples: {result.total_samples_evaluated:,}")
    print(f"Overall Accuracy: {result.overall_accuracy:.2%}")
    print(f"Crisis Recall: {result.crisis_recall:.2%}")
    print(f"Passes Safety: {'✅ YES' if result.passes_safety_threshold else '❌ NO'}")
    
    if result.safety_issues:
        print("\n⚠️ Safety Issues:")
        for issue in result.safety_issues:
            print(f"  - {issue}")
    
    print(f"\nResults saved to: {config.output_dir}")
    print("=" * 60)
    
    return 0 if result.passes_safety_threshold else 1


def cmd_download(args) -> int:
    """Download datasets command."""
    from .datasets import MentalChat16KLoader, PHQ9DatasetLoader, ClinicalDecisionLoader
    
    loaders = {
        "mentalchat16k": MentalChat16KLoader,
        "phq9_depression": PHQ9DatasetLoader,
        "clinical_decisions": ClinicalDecisionLoader,
    }
    
    datasets = list(loaders.keys()) if args.dataset == "all" else [args.dataset]
    
    for name in datasets:
        print(f"Downloading {name}...")
        loader = loaders[name]()
        success = loader.download()
        if success:
            print(f"  ✅ {name} downloaded successfully")
        else:
            print(f"  ❌ {name} download failed")
    
    return 0


def cmd_list(args) -> int:
    """List resources command."""
    if args.datasets:
        print("\nAvailable Datasets:")
        print("-" * 40)
        datasets = [
            ("mentalchat16k", "MentalChat16K - Conversational counseling benchmark"),
            ("phq9_depression", "PHQ-9 - Depression severity assessment"),
            ("clinical_decisions", "Clinical Decision Tasks - Triage reasoning"),
        ]
        for name, desc in datasets:
            print(f"  {name}: {desc}")
    
    if args.benchmarks:
        print("\nAvailable Benchmarks:")
        print("-" * 40)
        benchmarks = [
            ("crisis_detection", "Crisis keyword detection (20 cases)"),
            ("adversarial_cases", "Bypass attempt detection (20 cases)"),
            ("false_positives", "False positive prevention (25 cases)"),
            ("caution_cases", "Caution level detection (20 cases)"),
            ("session_progression", "Session trajectory analysis (10 cases)"),
        ]
        for name, desc in benchmarks:
            print(f"  {name}: {desc}")
    
    if args.results:
        results_dir = Path("feelwell/evaluation/results")
        if results_dir.exists():
            print("\nPrevious Evaluation Results:")
            print("-" * 40)
            for f in sorted(results_dir.glob("*_results.json"), reverse=True)[:10]:
                print(f"  {f.stem}")
        else:
            print("\nNo previous results found.")
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = setup_parser()
    args = parser.parse_args()
    
    if args.command == "run":
        return cmd_run(args)
    elif args.command == "download":
        return cmd_download(args)
    elif args.command == "list":
        return cmd_list(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
