# Video Generation Models Research

## Summary

As of mid-2026, the leading open-source video generation models are Wan 2.2, HunyuanVideo, LTX-2.3, and CogVideoX-1.5-5B. Wan 2.2 is the recommended choice for this project due to its balance of quality, VRAM requirements, and ecosystem support.

## Model Comparison

| Model | Params | VRAM (480p) | VRAM (720p) | Gen Time (5s clip, H100) | Quality (1-5) |
|-------|--------|-------------|-------------|--------------------------|---------------|
| Wan 2.2 14B (MoE, 27B total/14B active) | 14B active | 40-48 GB | 65-80 GB | ~4-5 min (480p), ~10-12 min (720p) | 4.5 |
| HunyuanVideo 13B | 13B | N/A | 60-80 GB (OOM risk) | ~12-18 min | 5.0 |
| LTX-2.3 22B | 22B | N/A | 24-32 GB (fp8) | ~5-8 min | 3.5 |
| CogVideoX-1.5-5B | 5B | N/A | 24-32 GB | ~8-12 min | 3.0 |
| Wan 2.1 1.3B | 1.3B | ~8 GB | N/A | ~2-3 min | 2.5 |

## Wan 2.2 — Our Primary Choice

### Why Wan 2.2

- **Best quality-to-cost ratio** in open-source video generation
- **MoE architecture** (27B total, 14B active per step) — gets quality of a massive model with efficiency of a smaller one
- **Trained on 65% more images and 83% more video** than Wan 2.1
- **Cinematic aesthetic control** — labels for lighting, composition, contrast, color tone
- **Multiple variants**: T2V (text-to-video), I2V (image-to-video), S2V (subject-to-video), VACE (all-in-one)
- **First/Last frame conditioning** — critical for scene chaining (Wan 2.2 FLF2V)
- **AMD ROCm officially supported** via xDiT for multi-GPU sequence parallelism
- **Diffusers integration** — HuggingFace pipeline ready

### Wan 2.2 Variants Available

| Variant | Use Case | HuggingFace |
|---------|----------|-------------|
| Wan2.2-T2V-A14B | Text to Video | Wan-AI/Wan2.2-T2V-A14B |
| Wan2.2-I2V-A14B | Image to Video (frame conditioning) | Wan-AI/Wan2.2-I2V-A14B |
| Wan2.2-S2V-14B | Subject-driven video (character consistency) | Wan-AI/Wan2.2-S2V-14B |
| Wan2.1-VACE-14B | All-in-one (edit, ref, compose) | Wan-AI/Wan2.1-VACE-14B |

### Generation Speed Benchmarks

- **A100 80GB, 480p, 5s clip**: ~4-5 minutes
- **H100 SXM, 480p, 5s clip**: ~3-4 minutes
- **H100 SXM, 720p, 5s clip**: ~10-12 minutes
- **Optimized (Baseten runtime, Hopper)**: 2.5x faster (~60s for a clip)
- **NVFP4 + Sparse (Blackwell)**: 4-step inference, dramatically faster

### Multi-GPU with xDiT (Sequence Parallelism)

AMD officially documents running Wan 2.1/HunyuanVideo across multiple MI300X GPUs using xDiT with Unified Sequence Parallelism (USP). This combines DeepSpeed-Ulysses and Ring Attention to split attention workloads across GPUs.

- Docker image: `rocm/pytorch-xdit`
- Supported GPUs: MI300X, MI325X, MI350X, MI355X (gfx942, gfx950)
- Scales linearly for concurrent jobs (no NVLink required for independent jobs)
- For single long clips: sequence parallelism splits token sequence across GPUs

## Character Consistency Approaches

| Method | Description | Compatibility |
|--------|-------------|---------------|
| **First/Last Frame Conditioning (FLF2V)** | Feed last frame of scene N as first frame of scene N+1 | Wan 2.2 native |
| **Subject-to-Video (S2V)** | Reference image of subject drives generation | Wan 2.2-S2V-14B |
| **VACE Reference** | Multi-task model supporting reference-to-video | Wan2.1-VACE-14B |
| **IP-Adapter** | Inject face/style embeddings into generation | Community adapters available |
| **Wan-Animate** | Character animation from reference + motion | Alibaba research |

## Long Video Generation

Current models generate 5-10 second clips natively. For longer content:

1. **Scene chaining** (our approach): Generate sequential 5s clips with frame conditioning for temporal coherence
2. **Sequence parallelism**: Split longer generations across multiple GPUs (research shows 2300 frames / ~1.5 min in 5 minutes on multi-GPU)
3. **Autoregressive models**: JoyAI-Echo (5 min), SANA-WM (1 min), Echo Infinity (infinite) — bleeding edge

## References

- [Wan 2.2 T2V Model Card](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B)
- [AMD ROCm xDiT Documentation](https://rocm.docs.amd.com/en/develop/how-to/rocm-for-ai/inference/xdit-diffusion-inference.html)
- [AMD Blog: Video Generation on ROCm with USP](https://rocm.blogs.amd.com/artificial-intelligence/video-generation-models/README.html)
- [AMD Blog: Multi-Node xDiT](https://rocm.blogs.amd.com/software-tools-optimization/multinode-hunyuanvideo-xdit/README.html)
- [Spheron GPU Guide for Video AI](https://www.spheron.network/blog/ai-video-generation-gpu-guide/)
- [Baseten: Wan 2.2 in <60s](https://www.baseten.co/blog/wan-2-2-video-generation-in-less-than-60-seconds/)
