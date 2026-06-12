# Technology Stack

## Core Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.12+ | ML ecosystem, diffusers, torch |
| Video Model | Wan 2.2 14B (MoE) | Best quality/cost, AMD ROCm support, frame conditioning |
| LLM (scripting) | DeepSeek V3 / GPT-4o-mini | Cheap, fast, good at structured output |
| TTS (free) | Edge TTS | Free, 300+ voices, no GPU needed |
| TTS (premium) | MisoTTS 8B | Natural speech, voice cloning, open weights |
| Video Assembly | FFmpeg | Industry standard, handles all formats |
| Subtitles | SRT from scene segments | Simple, aligned to scenes |
| API Framework | FastAPI | Async, fast, typed (GPU backend) |
| CLI | Typer + Rich | Clean CLI with progress display |
| GPU Inference | Diffusers + xDiT | HuggingFace standard + AMD multi-GPU |
| Containerization | Docker | Reproducible deployments |

## Model Weights

| Model | HuggingFace ID | Size | Use |
|-------|---------------|------|-----|
| Wan 2.2 T2V | Wan-AI/Wan2.2-T2V-A14B | ~30 GB | Text to video (first scene) |
| Wan 2.2 I2V | Wan-AI/Wan2.2-I2V-A14B | ~30 GB | Image/frame to video (scene chaining) |
| Wan 2.2 S2V | Wan-AI/Wan2.2-S2V-14B | ~30 GB | Subject-driven (character consistency) |
| Wan 2.1 VACE | Wan-AI/Wan2.1-VACE-14B | ~30 GB | All-in-one (edit, ref, compose) |
| MisoTTS 8B | MisoLabs/MisoTTS | ~16 GB (int8) | Natural TTS + voice cloning |

## Directory Structure

```
flow/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
├── uv.lock
├── Dockerfile               # Orchestrator container
├── Dockerfile.gpu           # GPU backend container
├── docs/
│   ├── research/            # Research notes
│   ├── architecture/        # System design docs
│   └── costs/               # Cost projections
├── src/
│   ├── flow/
│   │   ├── __init__.py
│   │   ├── __main__.py        # python -m flow
│   │   ├── cli.py             # CLI commands (generate, schedule)
│   │   ├── config.py          # TOML config + Pydantic models
│   │   ├── schemas.py         # ShotList, Scene, Character, GeneratedClip
│   │   ├── pipeline.py        # Main orchestration pipeline
│   │   ├── writer.py          # LLM script/shot-list generation
│   │   ├── generator.py       # GPU backend client + scene chaining
│   │   ├── validation.py      # Clip quality checks + retry logic
│   │   ├── characters.py      # Character bank (disk-persistent)
│   │   ├── postproduction.py  # TTS + subtitles + FFmpeg assembly
│   │   ├── tts_miso.py        # MisoTTS 8B integration
│   │   ├── publisher.py       # Multi-platform upload dispatcher
│   │   ├── publishers/
│   │   │   └── youtube.py     # YouTube resumable upload
│   │   └── scheduler.py       # Autonomous scheduling
│   └── gpu_backend/
│       ├── __init__.py
│       ├── server.py          # FastAPI inference server
│       ├── modal_server.py    # Modal serverless deployment
│       ├── client.py          # Backend client abstraction
│       └── xdit_parallel.py   # MI300X multi-GPU support
├── config/
│   ├── config.example.toml
│   └── characters/            # Character reference images
├── scripts/
│   └── deploy_modal.sh        # Modal deployment script
├── tests/
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_writer.py
│   └── test_characters.py
└── storage/                   # Generated outputs (gitignored)
```

## External Dependencies

| Service | Required | Purpose | Free Tier |
|---------|----------|---------|-----------|
| LLM API (DeepSeek/OpenAI) | Yes | Script generation | DeepSeek very cheap |
| GPU Cloud (Modal/RunPod) | Yes | Video + TTS generation | Modal: $30 free credits |
| Edge TTS | No (default TTS) | Voice narration | Unlimited free |
| TikTok Developer App | Optional | Auto-posting | Free |
| YouTube Data API | Optional | Auto-posting | Free (quota-limited) |
