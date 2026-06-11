# Cost Projections

## Scenario: 1-Hour Video Production

### What "1-Hour Video" Means

- 3600 seconds of content
- At 5 seconds per generated clip: **720 clips** needed
- At 10 seconds per clip (if using longer generation): **360 clips**

---

## Option A: Single A100 80GB (Modal)

**Resolution**: 480p (832×480)
**Clip length**: 5 seconds
**Generation time per clip**: ~4-5 minutes

| Metric | Value |
|--------|-------|
| Clips needed | 720 |
| Time per clip | ~4.5 min |
| Total GPU time | ~54 hours |
| GPU cost/hr (Modal A100) | ~$1.90 |
| **Total GPU cost** | **~$103** |
| LLM costs (script generation) | ~$0.50 |
| TTS costs (Edge TTS) | Free |
| **Total per 1-hour video** | **~$104** |
| **Production time** | **~54 hours (2.25 days)** |

---

## Option B: 8× MI300X Node (Parallel Generation)

**Resolution**: 480p
**Clip length**: 5 seconds
**Concurrent jobs**: 8 (one per GPU, each has 192GB)

| Metric | Value |
|--------|-------|
| Clips needed | 720 |
| Time per clip | ~4-5 min |
| Effective throughput | ~96 clips/hour (8 parallel) |
| Total wall time | **~7.5 hours** |
| GPU node cost/hr | ~$16-$24 |
| **Total GPU cost** | **~$120-$180** |
| **Production time** | **~7.5 hours** |

**Resolution**: 720p (higher quality)

| Metric | Value |
|--------|-------|
| Clips needed | 720 |
| Time per clip | ~10-12 min |
| Effective throughput | ~40-48 clips/hour |
| Total wall time | **~15-18 hours** |
| GPU node cost/hr | ~$16-$24 |
| **Total GPU cost** | **~$240-$432** |
| **Production time** | **~15-18 hours** |

---

## Option C: 8× MI300X with Optimized Runtime (Baseten-style 2.5x speedup)

**Resolution**: 480p, optimized inference

| Metric | Value |
|--------|-------|
| Clips needed | 720 |
| Time per clip | ~2 min (optimized) |
| Effective throughput | ~240 clips/hour |
| Total wall time | **~3 hours** |
| GPU node cost/hr | ~$16-$24 |
| **Total GPU cost** | **~$48-$72** |
| **Production time** | **~3 hours** |

---

## Summary Table

| Configuration | Resolution | Time to 1hr Video | Cost | $/minute of video |
|---------------|-----------|-------------------|------|-------------------|
| 1× A100 (Modal) | 480p | ~54 hours | ~$104 | ~$1.73 |
| 8× MI300X (parallel) | 480p | ~7.5 hours | ~$150 | ~$2.50 |
| 8× MI300X (parallel) | 720p | ~15-18 hours | ~$336 | ~$5.60 |
| 8× MI300X (optimized) | 480p | ~3 hours | ~$60 | ~$1.00 |
| Google Veo API (Lite) | 720p+ | ~1-2 hours | ~$180 | ~$3.00 |
| Google Veo API (Fast) | 720p+ | ~1 hour | ~$540 | ~$9.00 |

---

## Daily Content Production (Shorts: 60s each)

For a content channel posting 2 shorts per day:

| Configuration | Clips per video | Time per video | Daily cost | Monthly cost |
|---------------|----------------|----------------|-----------|-------------|
| 1× A100 (480p) | 12 clips | ~54 min | ~$3.40 | ~$102 |
| 8× MI300X (480p) | 12 clips | ~7 min | ~$3.70 | ~$111 |
| Google Veo Lite | 12 clips | ~5 min | ~$6.00 | ~$180 |

**For shorts content, the A100 is the most cost-effective option.**

---

## When to Use Each Option

| Use Case | Recommendation |
|----------|---------------|
| 1-3 short videos per day (60s) | Single A100 on Modal (~$100/month) |
| Long-form content (10-60 min) | 8× MI300X (parallel generation) |
| Maximum speed for long-form | 8× MI300X + optimized runtime |
| Testing/prototyping | Single A100, 480p |
| Production at scale (10+ videos/day) | Reserved MI300X node |

---

## Additional Costs (Fixed)

| Item | Cost | Frequency |
|------|------|-----------|
| LLM API (DeepSeek/OpenAI for scripts) | ~$5-$20 | Monthly |
| TTS (Edge TTS) | Free | - |
| TTS (ElevenLabs, if premium voice) | ~$5-$22 | Monthly |
| VPS (orchestrator, this server) | Already have | - |
| Domain/hosting | Minimal | Monthly |
| Upload-Post (auto-publishing) | Varies | Monthly |
