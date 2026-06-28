<div align="center">

# Flow

### OpenX Flow — Like Google Flow, but yours.

An open-source autonomous video generation pipeline. Give it a topic — it writes a script, generates AI video scene-by-scene, assembles a full production with narration and music, and publishes it.

No human in the loop.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/OpenX-Inc/flow/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenX-Inc/flow/actions/workflows/ci.yml)
[![GitHub Stars](https://img.shields.io/github/stars/OpenX-Inc/flow.svg?style=social)](https://github.com/OpenX-Inc/flow)

</div>

---

## What It Does

```
Topic → Script → Scene-by-Scene AI Video → Assembly → Publish
```

- **Writes** a narrated script with scene descriptions using an LLM
- **Generates** each scene as a 5-second AI video clip (Wan 2.2)
- **Chains** scenes with temporal coherence (last-frame conditioning)
- **Maintains** character consistency across all scenes
- **Assembles** clips with transitions, narration, subtitles, and music
- **Publishes** to TikTok, YouTube Shorts, and Instagram Reels

## The Vision

Build a 1-hour video in X hours for X dollars — fully autonomously.

| Target | Configuration | Time | Cost |
|--------|--------------|------|------|
| 60-second short | 1× A100 | ~1 hour | ~$2 |
| 10-minute video | 8× MI300X | ~1.5 hours | ~$30 |
| 1-hour film | 8× MI300X (optimized) | ~3-7 hours | ~$60-$180 |

No UI, no manual intervention. Feed it topics on a schedule and it produces content.

## Why This Exists

1. **Content creation makes money** but takes time most developers don't have
2. **Google Flow** proved scene-chaining filmmaking works — but it's closed, rate-limited, and expensive at scale
3. **Wan 2.2** is an open-source video model that rivals commercial offerings
4. **GPU access is cheap** — A100s at $1.50/hr, MI300X nodes at $16-24/hr
5. No open-source project combines all of this into a single autonomous pipeline

## How It Compares

| | Google Flow | LTX Studio | OpenMontage | **Flow (this)** |
|--|--|--|--|--|
| AI video generation | Veo 3.1 (closed) | Multiple (closed) | External APIs | **Self-hosted Wan 2.2** |
| Scene chaining | ✅ | ✅ | ❌ | ✅ |
| Character consistency | ✅ | ✅ | ❌ | ✅ |
| Fully autonomous | ❌ (interactive) | ❌ (interactive) | Partial | **✅** |
| Self-hosted | ❌ | ❌ | ✅ | **✅** |
| Cost at scale | $$$$ | $$$ | $$ | **$** |
| Fine-tuning | ❌ | ❌ | ❌ | **✅** |
| Open source | ❌ | ❌ | ✅ | **✅** |

## Architecture

```
┌─────────────────────────────────────┐
│         ORCHESTRATOR (VPS)           │
│                                      │
│  Scheduler → Writer → Generator →   │
│  Post-Production → Publisher         │
└──────────────────┬──────────────────┘
                   │ HTTP API
                   ▼
┌─────────────────────────────────────┐
│       GPU BACKEND (Cloud)            │
│                                      │
│  Wan 2.2 T2V / I2V / FLF2V / S2V   │
│  (Modal, RunPod, or self-hosted)     │
└─────────────────────────────────────┘
```

The orchestrator runs on any cheap VPS. The GPU backend is a separate service that runs on:

- **Modal** — Serverless A100, cheapest for low volume
- **RunPod** — Flexible, supports AMD MI300X
- **AWS / GCP** — Enterprise scale
- **Self-hosted** — Bare metal MI300X for maximum throughput

## Key Features

- **Scene chaining** — First/last frame conditioning ensures visual continuity
- **Character consistency** — Reference images and subject-driven generation (S2V)
- **Modular GPU backend** — Swap between Modal, RunPod, AWS, GCP, or bare metal
- **Fully headless** — No UI, no interaction. Cron-scheduled or event-triggered
- **Multi-platform publishing** — TikTok, YouTube Shorts, Instagram Reels
- **Cost-optimized** — $1-3/minute of video on A100, less with MI300X optimization
- **AMD MI300X native** — xDiT sequence parallelism for multi-GPU generation

## Supported Video Models

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| Wan 2.2 14B (primary) | 40-80 GB | High | ~4 min/clip (480p) |
| Wan 2.1 VACE 14B | 40-80 GB | High | ~4 min/clip |
| LTX-2.3 (lightweight) | 24-32 GB | Good | ~5-8 min/clip |

## Supported GPU Platforms

| Platform | GPUs Available | Pricing |
|----------|---------------|---------|
| Modal | A100 80GB | ~$1.90/hr |
| RunPod | A100, MI300X | ~$1.10-$3.00/hr |
| AWS (p4/p5) | A100, H100 | ~$2-$4/hr |
| GCP (a2/a3) | A100, H100 | ~$2-$4/hr |
| Self-hosted 8× MI300X | MI300X (192GB each) | ~$16-$24/hr (node) |

## Text-to-Speech & Voice Cloning

Narration is produced by a pluggable TTS layer. Pick a provider in config:

| Provider | Cost | Cloning | Notes |
|----------|------|---------|-------|
| `edge` | Free | ❌ | Microsoft online voices, CPU-only. Default. |
| `miso` | GPU | ✅ | [MisoTTS](https://huggingface.co/MisoLabs/MisoTTS) — natural speech + one-shot voice cloning. Runs locally or via an HTTP endpoint. |

```toml
[tts]
provider = "miso"
miso_endpoint = "https://your-gpu-host/"   # or leave empty to reuse gpu_backend.url / run locally
voice_sample = "config/voices/narrator.wav" # reference clip to clone
voice_transcript = "Transcript of the sample."
```

Bring your own backend without forking — subclass `TTSProvider` and register it:

```python
from pathlib import Path
from flow.tts import TTSProvider, register_provider

@register_provider
class MyTTS(TTSProvider):
    name = "mytts"
    output_ext = "wav"
    supports_cloning = True

    def synthesize(self, text, output_path, *, voice=None,
                   reference_audio=None, reference_transcript=None):
        ...  # write audio to output_path
        return Path(output_path)
```

Providers are stateless — they take text (and optionally a voice name or a
reference clip) and return an audio file. Nothing about your deployment leaks
into the core.

## Quick Start

> 🚧 Under active development. Pipeline implementation coming soon.

```bash
# Clone
git clone https://github.com/OpenX-Inc/flow.git
cd flow

# Install
uv sync

# Configure
cp config/config.example.toml config/config.toml
# Edit config.toml with your API keys and GPU backend

# Dry run (generates script only, no GPU needed)
python -m flow generate --topic "The history of the internet" --duration 60 --dry-run

# Generate a video
python -m flow generate --topic "The history of the internet" --duration 60

# Or run the scheduler for autonomous daily generation
python -m flow schedule
```

## Self-Hosted vs OpenX Flow (Cloud)

| | Self-Hosted (this repo) | OpenX Flow (managed) |
|--|--|--|
| **Setup** | You deploy, you manage | We handle everything |
| **GPU** | Your own (Modal, RunPod, etc.) | Our MI300X cluster |
| **Cost** | GPU rental only | Pay per video |
| **Control** | Full | API-based |
| **Best for** | Developers, high-volume | Creators, teams, agencies |

> **OpenX Flow** (managed service) — coming soon. Same pipeline, zero infrastructure.

## Documentation

- [System Architecture](docs/architecture/system-design.md)
- [Technology Stack](docs/architecture/tech-stack.md)
- [Cost Projections](docs/costs/projections.md)
- [Video Models Research](docs/research/video-models.md)
- [GPU Infrastructure Research](docs/research/gpu-infrastructure.md)
- [MI300X Multi-Instance Benchmarking](docs/research/mi300x-benchmarking.md)
- [Google Flow Analysis](docs/research/google-flow-analysis.md)
- [Publishing & Distribution](docs/research/publishing.md)

## Roadmap

- [ ] Core pipeline (writer → generator → assembly)
- [ ] GPU backend (Modal deployment with Wan 2.2)
- [ ] Scene chaining with first/last frame conditioning
- [ ] Character bank with reference images
- [ ] TTS + subtitle integration
- [ ] Auto-publishing to TikTok/YouTube/Instagram
- [ ] Scheduler for autonomous daily generation
- [ ] MI300X multi-GPU support via xDiT
- [ ] AWS + GCP backend support
- [ ] Quality validation and scene regeneration
- [ ] Fine-tuning pipeline for brand-specific style
- [ ] OpenX Flow managed service

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

We welcome contributions in all areas — GPU backend, pipeline logic, publishing integrations, documentation, and testing.

## License

MIT

## Credits

Built by [OpenX-Inc](https://github.com/OpenX-Inc). Inspired by [Google Flow](https://labs.google/fx/tools/flow) and [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo).
