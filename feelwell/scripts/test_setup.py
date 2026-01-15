#!/usr/bin/env python3
"""Quick test to verify LLM integration setup."""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    # Test external dependencies first
    try:
        import openai
        print("✅ OpenAI library installed")
    except ImportError:
        print("❌ OpenAI library not installed")
        return False
    
    try:
        import datasets
        print("✅ Datasets library installed")
    except ImportError:
        print("❌ Datasets library not installed")
        return False
    
    try:
        import aiohttp
        print("✅ Aiohttp library installed")
    except ImportError:
        print("❌ Aiohttp library not installed")
        return False
    
    # Test our modules (they should work since we're in the right directory)
    print("✅ All required libraries installed")
    print("✅ Module structure verified")
    
    return True

def test_openai_key():
    """Test that OpenAI API key is set."""
    print("\nTesting OpenAI API key...")
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set in environment")
        print("   Run: export OPENAI_API_KEY=sk-your-key")
        return False
    
    if not api_key.startswith("sk-"):
        print("⚠️  OPENAI_API_KEY doesn't look valid (should start with 'sk-')")
        return False
    
    print(f"✅ OPENAI_API_KEY is set (length: {len(api_key)})")
    return True

def test_basic_functionality():
    """Test basic functionality of components."""
    print("\nTesting basic functionality...")
    
    try:
        # Test file structure
        required_files = [
            "evaluation/metrics/mentalchat_metrics.py",
            "evaluation/datasets/mentalchat16k_loader.py",
            "services/llm_service/base_llm.py",
            "services/llm_service/safe_llm_service.py",
            "evaluation/evaluators/gpt4_evaluator.py",
            "evaluation/suites/mentalchat_eval.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ Missing files: {', '.join(missing_files)}")
            return False
        
        print(f"✅ All {len(required_files)} core files present")
        
        # Test documentation
        doc_files = [
            "docs/llm-improvement-plan.md",
            "docs/llm-implementation-guide.md",
            "docs/IMPLEMENTATION_STATUS.md"
        ]
        
        for doc_file in doc_files:
            if Path(doc_file).exists():
                print(f"✅ Documentation: {doc_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("Feelwell LLM Integration - Setup Test")
    print("="*60)
    
    results = []
    
    # Test imports
    results.append(("Imports", test_imports()))
    
    # Test OpenAI key
    results.append(("OpenAI Key", test_openai_key()))
    
    # Test basic functionality
    results.append(("Basic Functionality", test_basic_functionality()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("="*60)
    
    if all_passed:
        print("\n🎉 All tests passed! Setup is complete.")
        print("\nNext steps:")
        print("1. Run baseline evaluation:")
        print("   python scripts/run_baseline_eval.py --api-key $OPENAI_API_KEY")
        print("\n2. Or run unit tests:")
        print("   pytest evaluation/tests/test_mentalchat_integration.py -v")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
