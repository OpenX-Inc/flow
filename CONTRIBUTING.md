# Contributing to Creator

Thanks for your interest in contributing! This project is building an open-source autonomous video generation pipeline — a self-hosted alternative to Google Flow.

## How to Contribute

### Reporting Issues

- Use GitHub Issues for bugs, feature requests, or questions
- Include your hardware/GPU setup if relevant
- For video quality issues, include the prompt and generation parameters

### Development Setup

```bash
# Clone
git clone https://github.com/Toons-Official/creator.git
cd creator

# Install dependencies (requires uv)
uv sync

# Copy config
cp config/config.example.toml config/config.toml
```

### Project Structure

```
creator/
├── src/creator/       # Main pipeline code (orchestrator)
├── src/gpu_backend/   # GPU inference server
├── docs/              # Research and architecture docs
├── config/            # Configuration files
├── scripts/           # Setup and deployment scripts
└── tests/             # Test suite
```

### What We Need Help With

| Area | Skills | Priority |
|------|--------|----------|
| GPU Backend | PyTorch, Diffusers, CUDA/ROCm | High |
| Pipeline Orchestration | Python, async, task queues | High |
| Video Assembly | FFmpeg, Python | Medium |
| Publishing Integration | OAuth, REST APIs | Medium |
| Testing & CI | pytest, GitHub Actions | Medium |
| Documentation | Technical writing | Low |
| Fine-tuning | ML training, LoRA | Future |

### Contribution Guidelines

1. **Fork** the repo and create a feature branch from `main`
2. **Write tests** for new functionality
3. **Follow existing code style** — run linting before submitting
4. **Keep PRs focused** — one feature or fix per PR
5. **Document** any new configuration options or architecture decisions

### Code Standards

- Python 3.12+
- Type hints on all public functions
- Docstrings on modules and classes
- `ruff` for linting and formatting
- `pytest` for testing

### Architecture Principles

- **Modular**: Each pipeline stage is independent and replaceable
- **Backend-agnostic**: GPU backend is accessed via HTTP API — any provider works
- **Headless-first**: No UI needed; everything runs autonomously
- **Configuration-driven**: Behavior controlled via TOML config, not code changes

### Getting Started (Good First Issues)

Look for issues labeled `good-first-issue`. Typical starter tasks:

- Add a new TTS voice provider
- Improve prompt templates for scene generation
- Add a new publishing platform
- Write tests for existing modules
- Improve documentation

## Communication

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Design questions, architecture proposals
- **Pull Requests**: Code contributions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
