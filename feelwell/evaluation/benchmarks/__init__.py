"""Benchmark datasets for evaluation.

Each benchmark contains:
- input: The test input (message, session, etc.)
- expected: Expected output from the system
- metadata: Context about the test case (source, severity, etc.)
"""
from .loader import BenchmarkLoader, BenchmarkCase, BenchmarkSuite, BenchmarkResult

__all__ = ["BenchmarkLoader", "BenchmarkCase", "BenchmarkSuite", "BenchmarkResult"]
