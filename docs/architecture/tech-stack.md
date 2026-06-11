# Technology Choices

## Core Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.12+ | ML ecosystem, diffusers, torch |
| Video Model | Wan 2.2 14B (MoE) | Best quality/cost, AMD ROCm support, frame conditioning |
| LLM (scripting) | DeepSeek V3 / GPT-4o-mini | Cheap, fast, good at structured output |
| TTS | Edge TTS (default), ElevenLabs (premium) | Free tier available, 300+ voices |
| Video Assembly | FFmpeg | Industry standard, handles all formats |
| Subtitles | Whisper Large v3 | Best open-source speech recognition |
| Task Queue | Redis + RQ (or Celery) | Simple, reliable job management |
| API Framework | FastAPI | Async, fast, typed |
| GPU Inference | Diffusers + xDiT | HuggingFace standard + AMD multi-GPU support |
| Containerization | Docker | Reproducible deployments |

## Model Weights

| Model | HuggingFace ID | Size | Use |
|-------|---------------|------|-----|
| Wan 2.2 T2V | Wan-AI/Wan2.2-T2V-A14B | ~30 GB | Text to video (first scene) |
| Wan 2.2 I2V | Wan-AI/Wan2.2-I2V-A14B | ~30 GB | Image/frame to video (scene chaining) |
| Wan 2.2 S2V | Wan-AI/Wan2.2-S2V-14B | ~30 GB | Subject-driven (character consistency) |
| Wan 2.1 VACE | Wan-AI/Wan2.1-VACE-14B | ~30 GB | All-in-one (edit, ref, compose) |

## Directory Structure (Planned)

```
creator/
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── research/          # Research notes
│   ├── architecture/      # System design docs
│   └── costs/             # Cost projections
├── src/
│   ├── creator/
│   │   ├── __init__.py
│   │   ├── pipeline.py        # Main orchestration pipeline
│   │   ├── writer.py          # LLM script/shot-list generation
│   │   ├── characters.py      # Character bank management
│   │   ├── generator.py       # Video generation client (calls GPU backend)
│   │   ├── postproduction.py  # TTS, subtitles, music, assembly
│   │   ├── publisher.py       # Platform upload (TikTok, YT, IG)
│   │   ├── scheduler.py       # Cron/scheduling logic
│   │   └── config.py          # Configuration management
│   └── gpu_backend/
│       ├── __init__.py
│       ├── server.py          # FastAPI inference server
│       ├── models.py          # Model loading and management
│       └── workers.py         # Generation workers
├── config/
│   ├── config.example.toml
│   └── characters/            # Character reference images
├── storage/
│   ├── outputs/               # Final videos
│   ├── clips/                 # Individual scene clips
│   └── cache/                 # Model cache, temp files
├── scripts/
│   ├── setup_gpu.sh           # GPU backend setup script
│   └── deploy_modal.py        # Modal deployment script
├── tests/
├── Dockerfile                 # Orchestrator container
├── Dockerfile.gpu             # GPU backend container
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## External Dependencies

| Service | Required | Purpose | Free Tier |
|---------|----------|---------|-----------|
| LLM API (DeepSeek/OpenAI) | Yes | Script generation | DeepSeek very cheap |
| GPU Cloud (Modal/RunPod) | Yes | Video generation | Modal: $30 free credits |
| Edge TTS | No (but default) | Voice narration | Unlimited free |
| Pexels API | Optional | Stock footage fallback | Free with key |
| TikTok Developer App | Optional | Auto-posting | Free |
| YouTube Data API | Optional | Auto-posting | Free (quota-limited) |
| Redis | Optional | Job queue | Local or free tier |
