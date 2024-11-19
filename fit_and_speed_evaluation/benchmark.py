import requests
import csv
import json
from datetime import datetime
import time
import statistics

def get_installed_models():
    """Fetch all installed Ollama models."""
    try:
        response = requests.get('http://localhost:11434/api/tags')
        if response.status_code == 200:
            return [model['name'] for model in response.json()['models']]
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching models: {e}")
        return []

def query_model(model_name, prompt):
    """Query a specific model and return response with metrics."""
    try:
        start_time = time.time()
        
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model_name,
                'prompt': prompt,
                'stream': False
            }
        )
        
        if response.status_code != 200:
            return None, None, None
        
        end_time = time.time()
        response_data = response.json()
        
        # Calculate tokens per second
        total_tokens = response_data.get('eval_count', 0)
        elapsed_time = end_time - start_time
        tokens_per_second = total_tokens / elapsed_time if elapsed_time > 0 else 0
        
        return (
            response_data.get('response', '').strip(),
            tokens_per_second,
            total_tokens
        )
    except requests.exceptions.RequestException as e:
        print(f"Error querying model {model_name}: {e}")
        return None, None, None

def run_model_benchmark(model_name, prompt, num_runs=4):
    """Run multiple benchmarks for a single model."""
    results = []
    tokens_per_sec_list = []
    total_tokens_list = []
    
    for run in range(num_runs):
        print(f"  Run {run + 1}/{num_runs}...")
        response, tokens_per_sec, total_tokens = query_model(model_name, prompt)
        
        if response is not None:
            results.append({
                'response': response,
                'tokens_per_sec': tokens_per_sec,
                'total_tokens': total_tokens,
                'run_number': run + 1
            })
            tokens_per_sec_list.append(tokens_per_sec)
            total_tokens_list.append(total_tokens)
    
    if results:
        avg_tokens_per_sec = statistics.mean(tokens_per_sec_list)
        avg_total_tokens = statistics.mean(total_tokens_list)
        return results, avg_tokens_per_sec, avg_total_tokens
    return None, None, None

def main():
    # Create timestamp for the CSV filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f'ollama_benchmark_{timestamp}.csv'
    prompt = "Tell me about the world in 2 sentences"
    
    # Get all installed models
    models = get_installed_models()
    if not models:
        print("No models found or couldn't connect to Ollama")
        return
    
    # Prepare CSV file
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            'Model',
            'Run Number',
            'Response',
            'Tokens/Second',
            'Total Tokens',
            'Average Tokens/Second',
            'Average Total Tokens'
        ])
        
        # Query each model and log results
        for model in models:
            print(f"\nBenchmarking {model}...")
            results, avg_tokens_per_sec, avg_total_tokens = run_model_benchmark(model, prompt)
            
            if results:
                # Write individual run results
                for run_result in results:
                    writer.writerow([
                        model,
                        run_result['run_number'],
                        run_result['response'],
                        f"{run_result['tokens_per_sec']:.2f}",
                        run_result['total_tokens'],
                        f"{avg_tokens_per_sec:.2f}",
                        f"{avg_total_tokens:.1f}"
                    ])
                print(f"✓ {model} completed successfully")
                print(f"  Average tokens/sec: {avg_tokens_per_sec:.2f}")
            else:
                writer.writerow([model, "ERROR", "N/A", "N/A", "N/A", "N/A", "N/A"])
                print(f"✗ {model} failed")
    
    print(f"\nBenchmark complete! Results saved to {csv_filename}")

if __name__ == "__main__":
    main()