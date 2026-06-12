# System Architecture

## Overview

Flow is an open-source autonomous video generation pipeline — a self-hosted Google Flow alternative. It replicates Google Flow's scene-chaining filmmaking architecture using Wan 2.2 and other open-source models. Give it a topic and it produces a fully assembled, published video.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLOW PIPELINE (VPS)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐             │
│  │  TOPIC   │───▶│  WRITER   │───▶│  SHOT LIST   │             │
│  │  INPUT   │    │  (LLM)    │    │  (Scenes)    │             │
│  └──────────┘    └───────────┘    └──────┬───────┘             │
│                                          │                      │
│                                          ▼                      │
│  ┌───────────────────────────────────────────────────────┐     │
│  │              SCENE GENERATION LOOP                     │     │
│  │                                                        │     │
│  │  For each scene in shot_list:                          │     │
│  │    1. Build prompt (scene desc + style + camera)       │     │
│  │    2. Get character refs from Character Bank           │     │
│  │    3. Get prev_last_frame (if not first scene)         │     │
│  │    4. Call Video Model (T2V or I2V/FLF2V)             │     │
│  │    5. Validate output (quality check + retry)          │     │
│  │    6. Extract last frame for next scene               │     │
│  │    7. Store clip                                       │     │
│  └───────────────────────────┬───────────────────────────┘     │
│                                  │                              │
│                                  ▼                              │
│  ┌───────────────────────────────────────────────────────┐     │
│  │              POST-PRODUCTION                           │     │
│  │                                                        │     │
│  │  1. TTS narration (Edge TTS or MisoTTS 8B + cloning)  │     │
│  │  2. Subtitle generation                               │     │
│  │  3. Background music selection/generation             │     │
│  │  4. FFmpeg assembly (clips + audio + subs + music)    │     │
│  │  5. Optional upscale (Real-ESRGAN for 4K)            │     │
│  └───────────────────────────┬───────────────────────────┘     │
│                                  │                              │
│                                  ▼                              │
│  ┌───────────────────────────────────────────────────────┐     │
│  │              PUBLISHER                                 │     │
│  │                                                        │     │
│  │  1. Generate metadata (title, desc, hashtags via LLM)  │     │
│  │  2. Extract thumbnail                                  │     │
│  │  3. Upload to TikTok / YouTube / Instagram            │     │
│  │  4. Log results                                        │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              GPU BACKEND (Cloud)                                 │
│                                                                  │
│  Serves Wan 2.2 models + MisoTTS via HTTP API:                  │
│  - POST /generate/t2v  (text-to-video)                          │
│  - POST /generate/i2v  (image-to-video, frame conditioning)     │
│  - POST /generate/flf2v (first-last frame to video)            │
│  - POST /tts/generate  (MisoTTS speech with voice cloning)     │
│                                                                  │
│  Infrastructure options:                                         │
│  - Modal (A100 80GB, serverless)                                │
│  - RunPod (A100, MI300X)                                        │
│  - AWS / GCP (p4d, a2)                                          │
│  - Self-hosted 8× MI300X node                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Scheduler (Cron / Event-Driven)

- Triggers pipeline on schedule (e.g., daily at 2am)
- Can also be triggered manually or via webhook
- Manages queue of topics (file-based or LLM-generated)

### 2. Writer (LLM Script Engine)

- **Input**: Topic or keyword
- **Output**: Structured shot list (JSON)
- **LLM**: Any OpenAI-compatible API (DeepSeek, GPT-4o-mini, Ollama)
- Generates: narration script, scene descriptions, camera directions, character descriptions

Shot list schema:
```json
{
  "title": "The Story of...",
  "narration": "Full narration text...",
  "scenes": [
    {
      "id": 1,
      "duration": 5,
      "visual_prompt": "A young warrior standing on a cliff at sunset, cinematic wide shot",
      "camera": "slow dolly forward",
      "narration_segment": "In a world where...",
      "characters": ["warrior"]
    }
  ],
  "characters": {
    "warrior": {
      "description": "Young woman with dark braided hair, silver armor",
      "reference_image": null
    }
  }
}
```

### 3. Character Bank

- Stores reference images for recurring characters
- On first appearance: extract reference from generated scene
- On subsequent scenes: inject reference into I2V/S2V generation
- Persists across videos (disk-backed manifest.json)

### 4. Video Generation Backend

- Receives generation requests via HTTP API
- Runs Wan 2.2 models (T2V, I2V, FLF2V, S2V)
- Quality validation with automatic retry (up to 3x)
- Supports Modal (serverless), RunPod, and self-hosted

### 5. Post-Production

- **TTS**: Edge TTS (free) or MisoTTS 8B (natural, voice cloning)
- **Subtitles**: SRT generation from scene narration segments
- **Music**: Royalty-free library
- **Assembly**: FFmpeg concat + crossfade + audio mixing
- **Upscale**: Optional Real-ESRGAN for 4K output

### 6. Publisher

- TikTok Content Posting API (OAuth + upload)
- YouTube Data API v3 (resumable upload)
- Instagram Graph API (stub)
- LLM-generated metadata (titles, descriptions, hashtags)

## Data Flow

```
Topic (string)
  → Script + Shot List (JSON)
    → Per-scene video clips (MP4)
      → Assembled video + audio (MP4)
        → Published to platforms
```

## Key Design Decisions

1. **Headless/non-interactive**: No UI — fully autonomous
2. **Modular**: Each component is independent and replaceable
3. **Backend-agnostic**: GPU backend accessed via HTTP — any provider works
4. **Scene-based**: Videos built from 5s scenes, enabling parallelism and retry
5. **Character persistence**: Characters stay consistent across scenes and videos
6. **Quality gates**: Each clip validated before assembly, retry on failure
7. **Multi-provider TTS**: Free (Edge) or premium (MisoTTS with voice cloning)
