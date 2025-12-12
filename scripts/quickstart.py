#!/usr/bin/env python3
"""
Quick start script for setting up and testing the distributed LLM system
"""

import os
import json
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print the result"""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")
    print(f"Running: {cmd}")
    print("-" * 60)

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Error: {result.stderr}")

    return result.returncode == 0

def main():
    print("\n" + "="*60)
    print("DISTRIBUTED LLM SYSTEM - QUICK START GUIDE")
    print("="*60)

    # Step 1: Check Python version
    print("\n1. Checking Python version...")
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✓ Python {sys.version}")

    # Step 2: Check uv installation
    print("\n2. Checking uv installation...")
    if not run_command("uv --version", "Checking if uv is installed"):
        print("\n❌ uv is not installed. Please install uv first:")
        print("   curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("   Or visit: https://github.com/astral-sh/uv")
        sys.exit(1)

    # Step 3: Install dependencies with uv
    print("\n3. Installing dependencies with uv...")
    if not run_command("uv sync", "Installing project dependencies"):
        print("Failed to install dependencies. Please run 'uv sync' manually.")
        sys.exit(1)

    # Step 4: Create example config if it doesn't exist
    config_path = Path("config/workers.json")
    if not config_path.exists():
        print("\n4. Creating example configuration...")
        print("\nYou need to update the configuration with your actual worker IP addresses.")
        print("\nExample for Ollama workers:")
        example_config = {
            "workers": [
                {
                    "id": "my-mac-ollama",
                    "host": "192.168.1.100",  # CHANGE THIS
                    "port": 11434,
                    "type": "ollama",
                    "model": "llama2",
                    "max_concurrent_requests": 5
                }
            ]
        }

        with open(config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
        print(f"✓ Created example config at {config_path}")
        print("\n⚠️  IMPORTANT: Update the host IP addresses in config/workers.json")
    else:
        print(f"✓ Configuration file exists at {config_path}")

    # Step 4: Test configuration
    print("\n4. Testing worker connectivity...")
    print("Make sure your workers are running before proceeding:")
    print("\nFor Ollama workers:")
    print("  export OLLAMA_HOST=0.0.0.0:11434")
    print("  ollama serve")
    print("\nFor LM Studio workers:")
    print("  - Open LM Studio")
    print("  - Go to Settings → Server")
    print("  - Set Host to '0.0.0.0'")
    print("  - Start the server")

    input("\nPress Enter when your workers are ready...")

    # Step 5: Run test
    print("\n5. Running connectivity test...")
    if not run_command("python -m src.main --config config/workers.json --test",
                      "Testing worker connectivity"):
        print("\n❌ Worker test failed. Check:")
        print("   - Workers are running on the specified IPs")
        print("   - Firewall is not blocking connections")
        print("   - IP addresses in config are correct")
        sys.exit(1)

    # Step 6: Test the system
    print("\n6. Starting interactive demo...")
    print("You can now send prompts to your distributed LLM system!")
    print("\nCommands in interactive mode:")
    print("  Type your prompt and press Enter")
    print("  'status' - Show worker status")
    print("  'metrics' - Show detailed metrics")
    print("  'quit' or 'q' - Exit")

    run_command("uv run python -m src.main --config config/workers.json --interactive",
               "Starting interactive mode")

    print("\n" + "="*60)
    print("QUICK START COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Update config/workers.json with all your workers")
    print("2. Process files: uv run python scripts/process_directory.py -i examples/texts/ --preset research")
    print("3. Run benchmarks: uv run python scripts/benchmark.py")
    print("4. Read the full documentation in README.md")

if __name__ == "__main__":
    main()