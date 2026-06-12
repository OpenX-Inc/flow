# Changelog

## [0.1.0](https://github.com/OpenX-Inc/flow/commits/main) (2026-06-12)

### Features

* Core pipeline orchestrator (topic → video → publish)
* LLM-powered writer with structured shot list generation
* GPU backend: Wan 2.2 on Modal (A100 80GB) and self-hosted FastAPI
* Scene chaining with first/last frame conditioning (FLF2V)
* Two-pass parallel generation (keyframes → parallel FLF2V infill)
* Pipelined generation mode (overlap keyframe + video generation)
* Character bank with cross-video persistence
* MisoTTS 8B integration with one-shot voice cloning
* Post-production: Edge TTS, subtitles, FFmpeg assembly
* Publisher: TikTok Content Posting API, YouTube resumable upload
* Autonomous scheduler with LLM topic generation
* Quality validation with retry on failed clips
* xDiT multi-GPU sequence parallelism for MI300X
* GPU backend client abstraction (Modal, RunPod, self-hosted)
* DeepSeek and Ollama LLM provider support
* `--dry-run` mode for script-only generation

### Documentation

* System architecture design
* Technology stack decisions
* Cost projections (A100, MI300X, Grok API comparison)
* Video models research (Wan 2.2, HunyuanVideo, LTX, CogVideoX)
* GPU infrastructure research (MI300X pricing, throughput)
* Google Flow architecture analysis
* MI300X multi-instance benchmarking plan
* Publishing & distribution research
* Contributing guidelines
