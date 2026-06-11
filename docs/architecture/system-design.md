# System Architecture

## Overview

Creator is an open-source autonomous video generation pipeline that replicates Google Flow's filmmaking architecture using self-hosted open-source models. It transforms a topic into a fully produced, multi-scene video — and optionally publishes it.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CREATOR PIPELINE                          │
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
│  │    5. Validate output (quality check)                  │     │
│  │    6. Extract last frame for next scene               │     │
│  │    7. Store clip                                       │     │
│  └───────────────────────────────┬───────────────────────┘     │
│                                  │                              │
│                                  ▼                              │
│  ┌───────────────────────────────────────────────────────┐     │
│  │              POST-PRODUCTION                           │     │
│  │                                                        │     │
│  │  1. TTS narration generation (aligned to script)       │     │
│  │  2. Subtitle generation                               │     │
│  │  3. Background music selection/generation             │     │
│  │  4. FFmpeg assembly (clips + audio + subs + music)    │     │
│  │  5. Optional upscale (Real-ESRGAN for 4K)            │     │
│  └───────────────────────────────┬───────────────────────┘     │
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
                              │ API calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              GPU BACKEND (Remote)                                │
│                                                                  │
│  Serves Wan 2.2 models via HTTP API:                            │
│  - POST /generate/t2v  (text-to-video)                          │
│  - POST /generate/i2v  (image-to-video, frame conditioning)     │
│  - POST /generate/flf2v (first-last frame to video)            │
│  - GET  /status/:job_id                                         │
│  - GET  /result/:job_id                                         │
│                                                                  │
│  Infrastructure options:                                         │
│  - Modal (A100 80GB, serverless)                                │
│  - RunPod (MI300X, persistent or serverless)                    │
│  - Self-hosted 8× MI300X node                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Scheduler (Cron / Event-Driven)

- Triggers pipeline on schedule (e.g., daily at 2am)
- Can also be triggered manually or via webhook
- Manages queue of topics to produce

### 2. Writer (LLM Script Engine)

- **Input**: Topic or keyword
- **Output**: Structured shot list (JSON)
- **LLM**: DeepSeek V3 / GPT-4o-mini / Claude Haiku (cheap, fast)
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
- On first appearance: generate a reference image (via T2I or first scene extraction)
- On subsequent scenes: inject reference into I2V/S2V generation
- Persists across videos for brand consistency

### 4. Video Generation Backend

- Receives generation requests via HTTP API
- Runs Wan 2.2 models (T2V, I2V, FLF2V, S2V)
- Returns video clips as MP4/raw frames
- Supports batching and queuing

### 5. Post-Production

- **TTS**: Edge TTS (free, 300+ voices) or ElevenLabs (premium)
- **Subtitles**: Whisper-based alignment or edge-tts timestamps
- **Music**: Royalty-free library or AI-generated (MusicGen)
- **Assembly**: FFmpeg with crossfade transitions between scenes
- **Upscale**: Optional Real-ESRGAN for 4K output

### 6. Publisher

- Handles OAuth for each platform
- Generates platform-specific metadata via LLM
- Schedules posts for optimal times
- Handles retries and rate limits

## Data Flow

```
Topic (string)
  → Script + Shot List (JSON)
    → Per-scene video clips (MP4)
      → Assembled video + audio (MP4)
        → Published to platforms
```

## Key Design Decisions

1. **Headless/non-interactive**: No UI needed — fully autonomous
2. **Modular**: Each component is independent and replaceable
3. **Backend-agnostic**: GPU backend can be Modal, RunPod, self-hosted, or any HTTP endpoint
4. **Scene-based**: Videos are built from 5s scenes, enabling parallelism and retry
5. **Character persistence**: Characters stay consistent across scenes and across videos
6. **Quality gates**: Each generated clip is validated before assembly
