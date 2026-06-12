# MI300X Multi-Instance Benchmarking Plan

## Goal

Determine the maximum number of concurrent Wan 2.2 inference instances per MI300X GPU to optimize throughput for video generation.

## Background

Each MI300X has 192GB HBM3. Wan 2.2 at 480p uses ~45GB per instance (weights + working memory). Theoretically this allows 4 instances per GPU (32 total on an 8-GPU node), but real-world performance depends on compute contention, memory bandwidth saturation, and peak VRAM spikes during attention.

### Theoretical Limits

| Approach | Per GPU | Total (8 GPUs) |
|----------|---------|-----------------|
| No weight sharing (45GB each) | 4 | 32 |
| Shared weights (30GB shared + 18GB/instance) | 9 | 72 |

### What Needs Benchmarking

1. **VRAM peak usage** — What's the actual peak VRAM during Wan 2.2 inference at 480p? (may spike above 45GB during attention)
2. **Compute contention** — How much slower does each instance get as you add more? (1 vs 2 vs 3 vs 4 per GPU)
3. **Memory bandwidth saturation** — At what point does 5.3 TB/s bandwidth become the bottleneck?
4. **Optimal concurrency** — The sweet spot where total throughput (clips/hour) is maximized

## Benchmark Protocol

### Setup

- Hardware: 1× AMD Instinct MI300X (192GB)
- Software: ROCm 6.x, PyTorch 2.6+, Diffusers
- Model: `Wan-AI/Wan2.2-T2V-A14B-Diffusers` (fp16)
- Resolution: 480p (832×480)
- Frames: 81 (5 seconds at 16fps)
- Inference steps: 30

### Tests

#### Test 1: Baseline Single Instance

```bash
HIP_VISIBLE_DEVICES=0 python benchmark.py --instances 1
```

Record:
- Peak VRAM usage
- Time per clip
- GPU utilization %

#### Test 2: Scale Up Instances

```bash
# Run N concurrent instances on same GPU
HIP_VISIBLE_DEVICES=0 python benchmark.py --instances N
```

Test N = 1, 2, 3, 4

Record per N:
- Peak VRAM usage (total)
- Time per clip (each instance)
- Total throughput (clips/min)
- GPU compute utilization
- Memory bandwidth utilization

#### Test 3: Weight Sharing (Advanced)

Load model weights once in shared memory, spawn multiple inference workers that reference the same weights but have independent working memory.

```python
# Conceptual — needs diffusers/PyTorch multiprocessing support
model = load_model_shared()
workers = [InferenceWorker(model, gpu_id=0) for _ in range(N)]
```

#### Test 4: Full Node (8 GPUs)

Run optimal-per-GPU instances across all 8 GPUs:

```bash
# Example: 4 instances per GPU × 8 GPUs = 32 total
torchrun --nproc_per_node=32 benchmark_node.py
```

### Metrics to Collect

| Metric | Tool |
|--------|------|
| Peak VRAM | `rocm-smi --showmeminfo vram` |
| GPU utilization | `rocm-smi --showuse` |
| Memory bandwidth | ROCm Compute Profiler |
| Time per clip | Application timing |
| Throughput | clips/hour calculated |

## Expected Outcomes

| Instances/GPU | Expected Time/Clip | Expected Throughput/GPU | Notes |
|---------------|-------------------|------------------------|-------|
| 1 | ~4.5 min | 13 clips/hr | Baseline |
| 2 | ~6-7 min each | ~18 clips/hr | Some contention |
| 3 | ~8-10 min each | ~20 clips/hr | More contention |
| 4 | ~10-14 min each | ~18-24 clips/hr | Possibly diminishing |

The sweet spot is where **total throughput per GPU** peaks. Beyond that, adding instances just slows everything down.

## Decision Matrix

After benchmarking, use results to set the default `max_instances_per_gpu` config:

| Result | Recommendation |
|--------|---------------|
| 2 instances/GPU optimal | 16 parallel total, ~36 clips/hr |
| 3 instances/GPU optimal | 24 parallel total, ~60 clips/hr |
| 4 instances/GPU optimal | 32 parallel total, ~72-96 clips/hr |

## References

- [AMD ROCm: Maximizing vLLM instances on a single node](https://rocm.docs.amd.com/en/docs-6.4.2/how-to/rocm-for-ai/inference-optimization/workload.html#maximizing-vllm-instances-on-a-single-node)
- [AMD ROCm: Configure gpu_memory_utilization](https://rocm.docs.amd.com/en/docs-6.4.2/how-to/rocm-for-ai/inference-optimization/workload.html#configure-the-gpu-memory-utilization-parameter)
- [AMD Blog: Video Generation on ROCm with USP](https://rocm.blogs.amd.com/artificial-intelligence/video-generation-models/README.html)

## Status

**Not yet benchmarked.** Requires access to MI300X hardware. Results will update this document and inform the default configuration in `config.example.toml`.
