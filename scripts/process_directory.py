#!/usr/bin/env python3
"""
Process multiple text files (research papers) in parallel using distributed LLM workers
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from src.load_balancer import LoadBalancer
from src.worker import Worker
from src.config import load_workers_config, load_config, RequestConfig, merge_request_configs


def find_text_files(directory: str, extensions: List[str] = None) -> List[str]:
    """Find all text files in directory"""
    if extensions is None:
        extensions = ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.csv']

    files = []
    for ext in extensions:
        files.extend(Path(directory).rglob(f'*{ext}'))

    return [str(f) for f in files]


def read_file_content(file_path: str, max_chars: int = 10000) -> str:
    """Read content from file with optional character limit"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(max_chars)
            if len(content) == max_chars:
                content += "\n\n[Note: File truncated for processing]"
            return content
    except Exception as e:
        return f"Error reading file {file_path}: {e}"


async def process_files(workers: List[Worker], files: List[str],
                       prompts: List[str], output_file: str,
                       max_concurrent: int = 50,
                       request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
    """Process multiple files with given prompts"""

    # Prepare all tasks
    tasks = []
    for file_path in files:
        content = read_file_content(file_path)
        for prompt_template in prompts:
            # Replace {filename} and {content} in prompt
            prompt = prompt_template.format(
                filename=os.path.basename(file_path),
                content=content
            )
            tasks.append({
                'file': file_path,
                'prompt': prompt,
                'prompt_template': prompt_template
            })

    print(f"\nProcessing {len(files)} files with {len(prompts)} prompts each")
    print(f"Total tasks: {len(tasks)}")
    print(f"Max concurrent: {max_concurrent}")

    # Process with load balancer
    start_time = time.time()
    results = []

    async with LoadBalancer(workers) as lb:
        # Create batches to avoid overwhelming the system
        batch_size = min(max_concurrent, len(tasks))

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(tasks)-1)//batch_size + 1} ({len(batch)} tasks)")

            # Prepare prompts for batch
            batch_prompts = [task['prompt'] for task in batch]

            # Process batch
            if request_config:
                batch_results = await lb.process_batch(
                    batch_prompts,
                    **request_config.__dict__,
                    max_concurrent=batch_size
                )
            else:
                batch_results = await lb.process_batch(
                    batch_prompts,
                    max_concurrent=batch_size
                )

            # Combine results with metadata
            for task, result in zip(batch, batch_results):
                result_data = {
                    'file': task['file'],
                    'prompt_template': task['prompt_template'],
                    'prompt': task['prompt'],
                    'timestamp': datetime.now().isoformat(),
                    'success': result['success']
                }

                if result['success']:
                    result_data['response'] = result['result']
                else:
                    result_data['error'] = result['error']

                results.append(result_data)

            # Show progress
            completed = min(i + batch_size, len(tasks))
            progress = (completed / len(tasks)) * 100
            elapsed = time.time() - start_time
            eta = (elapsed / completed) * (len(tasks) - completed) if completed > 0 else 0

            print(f"Progress: {progress:.1f}% ({completed}/{len(tasks)}) | "
                  f"Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s")

    total_time = time.time() - start_time

    # Summary statistics
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful

    summary = {
        'timestamp': datetime.now().isoformat(),
        'files_processed': len(files),
        'prompts_used': len(prompts),
        'total_tasks': len(tasks),
        'successful': successful,
        'failed': failed,
        'success_rate': (successful / len(tasks)) * 100,
        'total_time_seconds': total_time,
        'tasks_per_second': len(tasks) / total_time,
        'results': results
    }

    # Save results
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Files processed: {len(files)}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(successful/len(tasks))*100:.1f}%")
    print(f"Total time: {total_time:.1f}s")
    print(f"Average speed: {len(tasks)/total_time:.2f} tasks/sec")
    print(f"\nResults saved to: {output_file}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Process multiple text files with distributed LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all .txt files with a single prompt
  python process_directory.py -i papers/ -p "Summarize this paper: {content}"

  # Use multiple prompts
  python process_directory.py -i papers/ \\
    -p "Extract key findings from: {content}" \\
    -p "What methodology is used in {filename}?"

  # Use preset prompts for research papers
  python process_directory.py -i papers/ --preset research

  # Custom configuration
  python process_directory.py -i papers/ -c config/workers.json \\
    -o results.json --max-concurrent 100
        """
    )

    parser.add_argument('-i', '--input', required=True,
                       help='Input directory containing text files')
    parser.add_argument('-o', '--output', default='processing_results.json',
                       help='Output file for results (default: processing_results.json)')
    parser.add_argument('-c', '--config', default='config/workers.json',
                       help='Worker configuration file')
    parser.add_argument('-s', '--settings',
                       help='Load balancer settings file')
    parser.add_argument('-p', '--prompt', action='append',
                       help='Prompt template (use {filename} and {content} placeholders)')
    parser.add_argument('--preset', choices=['research', 'summary', 'analysis'],
                       help='Use preset prompt templates')
    parser.add_argument('--max-concurrent', type=int, default=50,
                       help='Maximum concurrent requests (default: 50)')
    parser.add_argument('--extensions', nargs='+',
                       default=['.txt', '.md', '.py', '.js', '.html', '.css', '.json'],
                       help='File extensions to process')
    parser.add_argument('--max-chars', type=int, default=10000,
                       help='Maximum characters per file to read (default: 10000)')

    args = parser.parse_args()

    # Preset prompts
    preset_prompts = {
        'research': [
            "Extract the main research question from this paper: {content}",
            "Summarize the methodology used in {filename}: {content}",
            "What are the key findings of this paper? {content}",
            "Identify the limitations mentioned in this study: {content}",
            "Suggest future research directions based on {filename}: {content}"
        ],
        'summary': [
            "Provide a concise summary of this document: {content}",
            "Extract the main points from {filename}: {content}",
            "What is the central argument in this paper? {content}"
        ],
        'analysis': [
            "Analyze the strengths and weaknesses of this paper: {content}",
            "How does this work contribute to the field? {content}",
            "What innovative approaches are presented in {filename}? {content}"
        ]
    }

    # Get prompts
    prompts = []
    if args.preset:
        prompts.extend(preset_prompts[args.preset])
    if args.prompt:
        prompts.extend(args.prompt)

    if not prompts:
        print("Error: No prompts specified. Use -p or --preset")
        sys.exit(1)

    # Check input directory
    if not os.path.exists(args.input):
        print(f"Error: Input directory not found: {args.input}")
        sys.exit(1)

    # Load worker configuration
    if not os.path.exists(args.config):
        print(f"Error: Worker configuration not found: {args.config}")
        sys.exit(1)

    try:
        # Load workers
        config_data = load_workers_config(args.config)
        workers = []
        for worker_data in config_data:
            from src.worker import Worker, WorkerType
            workers.append(Worker(
                id=worker_data['id'],
                host=worker_data['host'],
                port=worker_data['port'],
                worker_type=WorkerType(worker_data['type']),
                model=worker_data['model'],
                max_concurrent_requests=worker_data.get('max_concurrent_requests', 5)
            ))

        # Load settings if provided
        settings = None
        if args.settings and os.path.exists(args.settings):
            settings = load_config(args.settings)

        # Find files
        print(f"Searching for files in {args.input}...")
        files = find_text_files(args.input, args.extensions)
        print(f"Found {len(files)} files")

        if not files:
            print("No files found matching the criteria")
            sys.exit(1)

        # Process files
        asyncio.run(process_files(
            workers, files, prompts, args.output,
            args.max_concurrent, settings
        ))

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()