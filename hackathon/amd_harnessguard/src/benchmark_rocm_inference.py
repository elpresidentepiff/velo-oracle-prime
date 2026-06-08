import time
import torch
import numpy as np
import argparse

def benchmark_inference(device_name="cpu", num_iterations=100, batch_size=128):
    print(f"\n--- AMD ROCm Performance Benchmark ---")
    print(f"Target Device: {device_name}")
    print(f"Batch Size: {batch_size} | Iterations: {num_iterations}")

    # Check for ROCm / CUDA
    if device_name == "rocm" or device_name == "cuda":
        if not torch.cuda.is_available():
            print("ERROR: ROCm/CUDA device not found. Falling back to CPU for demonstration.")
            device = torch.device("cpu")
        else:
            device = torch.device("cuda")
            print(f"ROCm Device Detected: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")

    # Simulate a deep embedding / classification model
    # We use a large-ish tensor to simulate MI300X HBM bandwidth usage
    input_dim = 1024
    output_dim = 512
    
    weights = torch.randn(input_dim, output_dim).to(device)
    inputs = torch.randn(batch_size, input_dim).to(device)
    
    # Warmup
    print("Warming up...")
    for _ in range(10):
        _ = torch.matmul(inputs, weights)
    
    if device.type == 'cuda':
        torch.cuda.synchronize()

    print("Running benchmark...")
    start_time = time.perf_counter()
    
    for _ in range(num_iterations):
        # Simulated "Agentic Inference" step
        _ = torch.matmul(inputs, weights)
        
    if device.type == 'cuda':
        torch.cuda.synchronize()
        
    end_time = time.perf_counter()
    total_time = end_time - start_time
    avg_latency = (total_time / num_iterations) * 1000 # ms
    throughput = (num_iterations * batch_size) / total_time # signals/sec

    print(f"\nResults ({device_name.upper()}):")
    print(f"  Total Time: {total_time:.4f}s")
    print(f"  Avg Latency: {avg_latency:.2f}ms")
    print(f"  Throughput: {throughput:.2f} signals/sec")
    
    return {
        "device": device_name,
        "latency": avg_latency,
        "throughput": throughput
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard ROCm Benchmark")
    parser.add_argument("--device", choices=["cpu", "rocm"], default="cpu")
    args = parser.parse_args()
    
    benchmark_inference(args.device)
