# Google Flow Architecture Analysis

## What Google Flow Is

Google Flow is Google's AI filmmaking platform (launched 2025, major update at I/O 2026). It's powered by Veo 3.1 and Gemini Omni. It is NOT open source — it's a cloud service.

## Core Architecture (What We're Replicating)

Flow is an **orchestration layer** on top of a video generation model. The key insight: it doesn't generate hour-long videos in one pass. It generates **sequences of short clips** with continuity mechanisms.

### Flow's Pipeline

```
1. User provides story/concept
2. LLM decomposes into scene descriptions (shot list)
3. For each scene:
   a. Character reference images are injected
   b. Previous scene's last frame is used as conditioning
   c. Camera/style parameters are applied
   d. Video model generates 5-10s clip
4. Clips are assembled with transitions
5. Audio (dialogue, SFX, ambient) is generated/synced
6. Final output is a cohesive multi-scene video
```

### Key Features We Need to Replicate

| Feature | How Flow Does It | Our Implementation |
|---------|-----------------|-------------------|
| **Scene sequencing** | Storyboard UI with per-shot prompts | LLM auto-generates shot list from topic |
| **Character consistency** | Face/voice lock, reference images (up to 3) | Wan 2.2 S2V + first-frame conditioning |
| **Temporal coherence** | Last-frame → next-scene conditioning | Wan 2.2 FLF2V (First-Last Frame to Video) |
| **Camera control** | Per-shot camera angle/motion | Prompt engineering + Wan camera tokens |
| **Multi-turn editing** | Iterative refinement per scene | Regenerate individual scenes in pipeline |
| **Audio** | Native Veo 3.1 audio generation | Separate TTS + music pipeline |
| **4K output** | Veo native | Upscale post-processing (Real-ESRGAN) |

### What Makes Flow Special (and Replicable)

1. **Iterative consistency**: "Every edit builds on the one before" — this is just last-frame conditioning chained across scenes
2. **Reference bank**: Store character appearances and reuse across all scenes — we do this with a character registry + S2V/I2V
3. **Shot-level control**: Each scene has independent prompt, camera, duration — our pipeline does this naturally since each scene is a separate generation call

## What Flow Does That's Hard to Replicate

1. **Native audio in video generation** — Veo 3.1 generates synchronized dialogue with lip sync. We'd need a separate audio pipeline.
2. **Interactive editing UI** — We don't need this (headless system), but it's what makes Flow user-friendly.
3. **Gemini Omni "any-to-any"** — Feed existing video/images and get video out. We partially replicate with I2V/VACE.

## Our Competitive Advantages Over Flow

1. **Cost**: After GPU rental, per-video cost is much lower at scale
2. **No rate limits**: Flow has credit limits; we generate unlimited
3. **Fine-tuning**: Can fine-tune Wan 2.2 on our brand's visual style
4. **Full automation**: No human in the loop — topic to published video
5. **Ownership**: Full control over output, no platform dependency
6. **Customization**: Any duration, any style, any posting schedule

## Flow Pricing (for comparison)

| Tier | Cost |
|------|------|
| Veo 3.1 Lite | $0.05/sec of video |
| Veo 3.1 Fast | $0.15/sec |
| Veo 3.1 Standard | $0.40/sec |
| Veo 3.0 Full | $0.75/sec |

A 60-second video (12 × 5s clips) via Veo API:
- Lite: $3/video
- Fast: $9/video
- Standard: $24/video

## References

- [Google Flow Product Page](https://labs.google/fx/tools/flow/changelogs)
- [Google Blog: Flow AI Filmmaking](https://blog.google/innovation-and-ai/products/google-flow-veo-ai-filmmaking-tool/)
- [MindStudio: How to Use Google Flow](https://www.mindstudio.ai/blog/how-to-use-google-flow-gemini-omni-video-editing)
- [Flow Support: Get Started](https://support.google.com/flow/answer/16353333)
