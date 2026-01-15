#!/usr/bin/env python3
"""Process evaluation results from a failed run.

This script can recover results from an evaluation that completed
but failed during the report generation step.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.metrics.mentalchat_metrics import ClinicalEvaluation


def process_results(evaluations_file: str, model_name: str = "feelwell-baseline"):
    """Process evaluation results and generate report.
    
    Args:
        evaluations_file: Path to JSON file with evaluations
        model_name: Name of the model
    """
    print(f"\n📊 Processing evaluation results...")
    print(f"File: {evaluations_file}")
    print(f"Model: {model_name}\n")
    
    # Load evaluations
    with open(evaluations_file, 'r') as f:
        data = json.load(f)
    
    evaluations = [ClinicalEvaluation(**e) for e in data['evaluations']]
    
    print(f"✅ Loaded {len(evaluations)} evaluations\n")
    
    # Calculate metrics
    metrics = {}
    for metric_name in [
        'active_listening',
        'empathy_validation',
        'safety_trustworthiness',
        'open_mindedness',
        'clarity_encouragement',
        'boundaries_ethical',
        'holistic_approach'
    ]:
        scores = [getattr(e, metric_name) for e in evaluations]
        metrics[metric_name] = {
            'average': sum(scores) / len(scores),
            'min': min(scores),
            'max': max(scores),
            'count': len(scores)
        }
    
    # Calculate overall
    overall_scores = [e.overall_score for e in evaluations]
    overall_avg = sum(overall_scores) / len(overall_scores)
    
    # Calculate pass rate (threshold 7.5)
    pass_count = sum(1 for e in evaluations if e.overall_score >= 7.5)
    pass_rate = (pass_count / len(evaluations)) * 100
    
    # Print results
    print("="*60)
    print(f"Evaluation Results for {model_name}")
    print("="*60)
    print(f"Test Cases: {len(evaluations)}")
    print(f"Average Score: {overall_avg:.2f}/10")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print(f"\nMetric Scores:")
    
    for metric_name, scores in metrics.items():
        display_name = metric_name.replace('_', ' ').title()
        print(f"  {display_name}: {scores['average']:.2f}/10")
    
    # Check threshold
    if overall_avg >= 7.5:
        print("\n✅ Meets minimum quality threshold (7.5/10)")
    else:
        gap = 7.5 - overall_avg
        print(f"\n⚠️  Below minimum quality threshold (7.5/10) - Gap: {gap:.2f} points")
    
    # Save results
    output_dir = Path("evaluation_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f"{model_name}_{timestamp}.json"
    
    result = {
        "model_name": model_name,
        "timestamp": timestamp,
        "total_cases": len(evaluations),
        "overall_average": overall_avg,
        "pass_rate": pass_rate,
        "metrics": metrics,
        "evaluations": [e.__dict__ for e in evaluations]
    }
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n📁 Results saved to: {output_file}")
    print("\n" + "="*60)
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_eval_results.py <evaluations_file> [model_name]")
        print("\nExample:")
        print("  python process_eval_results.py /tmp/evaluations.json feelwell-baseline")
        sys.exit(1)
    
    evaluations_file = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "feelwell-baseline"
    
    process_results(evaluations_file, model_name)
