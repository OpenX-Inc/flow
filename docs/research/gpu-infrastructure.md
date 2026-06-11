# GPU Infrastructure Research

## Target Hardware: 8× AMD Instinct MI300X

### Specifications (per GPU)

| Spec | Value |
|------|-------|
| Architecture | CDNA 3 |
| VRAM | 192 GB HBM3 |
| Memory Bandwidth | 5.3 TB/s |
| FP16 Performance | 1.3 PFLOPS |
| Total (8× node) | 1.5 TB VRAM, 42.4 TB/s bandwidth |

### What 1.5TB VRAM Enables

- Run Wan 2.2 14B at 720p with massive headroom
- Generate longer clips (10-30s+) via sequence parallelism
- Run multiple concurrent generation jobs (up to 8 independent 480p jobs simultaneously)
- No quantization needed — run at full precision for maximum quality

### Rental Pricing (June 2026)

| Provider | MI300X Price/GPU/hr | 8× Node/hr | Notes |
|----------|--------------------:|------------:|-------|
| Spot (cheapest) | ~$0.50-$0.95 | ~$4-$8 | Variable availability |
| RunPod | ~$2.50-$3.00 | ~$20-$24 | Self-service, easy |
| Azure (ND MI300X v5) | ~$4-$5 | ~$32-$40 | Enterprise SLA |
| Hot Aisle | ~$2-$3 | ~$16-$24 | AMD-exclusive cloud |

### Alternative: Single A100 80GB (Modal)

| Spec | Value |
|------|-------|
| VRAM | 80 GB |
| Cost | ~$1.10-$2.50/hr |
| Wan 2.2 480p | ✅ Comfortable (~4-5 min/clip) |
| Wan 2.2 720p | ⚠️ Tight (65-80GB needed) |
| Concurrent jobs | 1 at a time |

### Recommended Strategy

**Phase 1 (MVP):** Single A100 on Modal — $1.50-2/hr, 480p generation, ~12 clips/hour
**Phase 2 (Scale):** 8× MI300X — parallel generation, 720p, longer clips, higher throughput

## Software Stack for AMD MI300X

- **ROCm** 6.x+ (AMD's GPU compute platform)
- **PyTorch** with ROCm backend
- **xDiT** — Diffusion Transformer inference engine with sequence parallelism
- **Docker**: `rocm/pytorch-xdit` (pre-built, optimized)
- **Diffusers** (HuggingFace) — pipeline abstractions

## Throughput Estimates

### Single A100 80GB (480p, 5s clips)

- ~4-5 min per clip
- ~12-15 clips per hour
- 1-hour video (720 clips × 5s) = ~50-60 hours of GPU time
- Cost: ~$75-$120

### 8× MI300X (480p, 5s clips, independent parallel jobs)

- 8 concurrent generations
- ~12 clips per GPU per hour × 8 = ~96 clips/hour
- 1-hour video (720 clips) = ~7.5 hours
- Cost at $20/hr: ~$150

### 8× MI300X (720p, 5s clips, independent parallel jobs)

- 8 concurrent 720p generations (each GPU has 192GB, only needs 65-80GB)
- ~5-6 clips per GPU per hour × 8 = ~40-48 clips/hour
- 1-hour video (720 clips) = ~15-18 hours
- Cost at $20/hr: ~$300-$360

### 8× MI300X (720p, sequence parallel for longer clips)

- Use all 8 GPUs for one 30s+ clip generation
- Theoretical: generate 30s clips in ~15-20 min
- 1-hour video (120 × 30s clips) = ~30-40 hours
- Still experimental for this clip length

## References

- [AMD MI300X Platform Specs](https://instinct.docs.amd.com/projects/system-acceptance/en/latest/gpus/mi300x.html)
- [Thunder Compute: MI300X Pricing](https://www.thundercompute.com/blog/amd-mi300x-pricing)
- [gpus.io: MI300X Price Comparison](https://gpus.io/en/gpus/mi300)
- [Azure ND MI300X v5](https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/introducing-the-new-azure-ai-infrastructure-vm-series-nd-mi300x-v5/4145152)
