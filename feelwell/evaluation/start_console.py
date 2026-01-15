#!/usr/bin/env python3
"""Start the Feelwell Test Console.

This script starts both the API server and provides instructions
for running the webapp.

Usage:
    python -m feelwell.evaluation.start_console
    
    # Or with custom port
    python -m feelwell.evaluation.start_console --port 8080
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Start Feelwell Test Console API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("  FEELWELL TEST CONSOLE")
    print("=" * 60)
    print(f"\n  API Server starting on http://localhost:{args.port}")
    print("\n  To start the webapp, run in another terminal:")
    print("    cd feelwell/webapp && npm install && npm run dev")
    print("\n  Then open http://localhost:5173 in your browser")
    print("\n" + "=" * 60 + "\n")
    
    try:
        from .api.server import run_server
        run_server(host=args.host, port=args.port)
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        print("\nInstall required packages:")
        print("  pip install fastapi uvicorn pydantic")
        sys.exit(1)


if __name__ == "__main__":
    main()
