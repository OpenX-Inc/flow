# Changelog

## [0.2.0](https://github.com/OpenX-Inc/flow/compare/v0.2.0...v0.2.0) (2026-06-24)


### Features

* 'The Last Library' — 2.5 min AI short film, 30 scenes, narrated ([b528fbb](https://github.com/OpenX-Inc/flow/commit/b528fbbe41dd19c08b781d3a1fc4a615df8d22d9))
* 20-clip benchmark batch — underwater, space, nature, urban, abstract ([2c23f4d](https://github.com/OpenX-Inc/flow/commit/2c23f4de06412e79f9a25dd096875c3d37307255))
* add --dry-run mode to generate command (script only, no GPU) ([e0fa24b](https://github.com/OpenX-Inc/flow/commit/e0fa24bc1a76d7148772a8072f829eb7cca14b85))
* add autonomous scheduler with topic generation ([1b64f9b](https://github.com/OpenX-Inc/flow/commit/1b64f9b4cab8a5a453b48c899f50af1b49e8cfd2))
* add character bank for cross-scene and cross-video consistency ([0179c24](https://github.com/OpenX-Inc/flow/commit/0179c2430935519daff2fea358f4b236d547e41d))
* add core module scaffold (config, schemas, CLI entry point) ([41adc18](https://github.com/OpenX-Inc/flow/commit/41adc18d7aad64a84b453b45712aa842b75f617a))
* add DeepSeek and Ollama LLM provider support ([7fec793](https://github.com/OpenX-Inc/flow/commit/7fec79388ec936305582267236cc90be6f952131))
* add generated video sample (242KB, 5s @ 16fps) ([190f812](https://github.com/OpenX-Inc/flow/commit/190f812355bb7f5dfc171a04ed7dfed863464d4d))
* add GPU backend client abstraction (Modal, RunPod, self-hosted) ([f228256](https://github.com/OpenX-Inc/flow/commit/f2282567514e4c66184e072be1b606af5a52f307))
* add GPU backend package scaffold ([4320b3b](https://github.com/OpenX-Inc/flow/commit/4320b3b8e85a62831eeeb69a8c28f43173c4e9d1))
* add keyframe generator for scene boundary images (Pass 1) ([22aaef3](https://github.com/OpenX-Inc/flow/commit/22aaef36d1d3885b100a69137fe227c043b02bac))
* add LLM-powered writer for script and shot list generation ([19f9a1a](https://github.com/OpenX-Inc/flow/commit/19f9a1aa042b5a260346464ef4e245866e8a7396))
* add MisoTTS 8B with one-shot voice cloning support ([0f0760e](https://github.com/OpenX-Inc/flow/commit/0f0760e11c020facc89a526ba9e327810ec2141a))
* add Modal deployment for Wan 2.2 GPU backend (A100 80GB) ([78dc023](https://github.com/OpenX-Inc/flow/commit/78dc023c1ff6ca1e2d2163fac427f35f7de34cdd))
* add parallel FLF2V generator for concurrent scene generation (Pass 2) ([1ad810e](https://github.com/OpenX-Inc/flow/commit/1ad810ecc31e17e0ba4671b79dc1c7a256f1911f))
* add pipeline orchestrator ([c01affc](https://github.com/OpenX-Inc/flow/commit/c01affc77d9036102dac5b4c1f0a75030b7bd840))
* add pipelined_flf2v mode (overlaps keyframe + video generation) ([e7946b0](https://github.com/OpenX-Inc/flow/commit/e7946b07799edcd9092aca41ce243162c7752187))
* add post-production (TTS, subtitles, FFmpeg assembly) ([c91cfee](https://github.com/OpenX-Inc/flow/commit/c91cfee4e6cee6b0c0f09e0e93fbfae682576382))
* add publisher module (TikTok, YouTube, Instagram stubs) ([8bb0d23](https://github.com/OpenX-Inc/flow/commit/8bb0d2379d924231155f1c04b888a4ecdb1ce956))
* add quality validation with retry on failed clip generation ([bded333](https://github.com/OpenX-Inc/flow/commit/bded33334322979e79ded4b4cfe26c53f93e7cb8))
* add standalone FastAPI GPU backend server (RunPod/self-hosted) ([36a465c](https://github.com/OpenX-Inc/flow/commit/36a465ccee06b25c54d242dbc9f2fd07c7c76bdb))
* add video generator with scene chaining (first-frame conditioning) ([e6039a0](https://github.com/OpenX-Inc/flow/commit/e6039a0b4ecf00177e47fb6eedcd2d7b625167be))
* add xDiT multi-GPU sequence parallelism for MI300X ([a29da98](https://github.com/OpenX-Inc/flow/commit/a29da980a188eebdc9053a1fb6a8e6017842f3fd))
* first benchmark — Wan 2.2 I2V generation on Modal A100 ([5a08ea1](https://github.com/OpenX-Inc/flow/commit/5a08ea14e50c5109c35f59326ee8ed59295576d4))
* first benchmark — Wan 2.2 I2V on Modal A100 ([6c93a77](https://github.com/OpenX-Inc/flow/commit/6c93a77825df3fd5a25a444d9707897a1dba31ce))
* full benchmark suite — 9 videos, 2 narratives, cost analysis ([88a7770](https://github.com/OpenX-Inc/flow/commit/88a777070864a761d55c0daa01b0474e4ae1a126))
* **gpu:** add flf2v + vace endpoints to Modal backend ([c2741c9](https://github.com/OpenX-Inc/flow/commit/c2741c93c13bc4700dcb209cee0f171a02face2b))
* implement TikTok upload via Content Posting API ([af5dc38](https://github.com/OpenX-Inc/flow/commit/af5dc3855e17c5cd4b9af9ef6ac17d22f37c3346))
* implement YouTube Shorts upload with resumable upload protocol ([31de3d1](https://github.com/OpenX-Inc/flow/commit/31de3d1dccff86b72de0348003458d6d7219dd0b))
* integrate two-pass parallel generation into pipeline (generation_mode config) ([6feac98](https://github.com/OpenX-Inc/flow/commit/6feac98810cbdaabf3ebdb35155494ff992a54cb))
* narrated benchmark — full pipeline (video + TTS + assembly) ([3fcd40e](https://github.com/OpenX-Inc/flow/commit/3fcd40eacb5f8973b568c649bbded6c9c8342a1d))
* stitch benchmark scenes into full videos ([b4d301f](https://github.com/OpenX-Inc/flow/commit/b4d301fa489ed50ce7bff934fd61ac36e8221109))


### Bug Fixes

* **release:** revert untagged 0.2.0 bump back to 0.1.0 ([15d5eea](https://github.com/OpenX-Inc/flow/commit/15d5eeac30f4d44fa05b0cbaf7a65c222cea7cc8))


### Documentation

* add CI badge and dry-run usage to README ([3b2b796](https://github.com/OpenX-Inc/flow/commit/3b2b7963fea83fa6a590380acd48127aa2141980))
* add contributing guidelines ([c511ccf](https://github.com/OpenX-Inc/flow/commit/c511ccf5d134b14d2b5acfa1b706f4023ed30c6a))
* add cost projections for video generation at scale ([c4fdeff](https://github.com/OpenX-Inc/flow/commit/c4fdeffe5bf114ba87cc1c23f7b4734b921d092d))
* add example configuration file ([1c99b03](https://github.com/OpenX-Inc/flow/commit/1c99b03b2020b3be650e09ac3702e12e50803128))
* add Google Flow architecture analysis ([7c54b68](https://github.com/OpenX-Inc/flow/commit/7c54b6894c321819ee8201ced719b401788b2e49))
* add GPU infrastructure research (MI300X, A100, pricing, throughput) ([27417e0](https://github.com/OpenX-Inc/flow/commit/27417e0cb39d9db5d36fc0113405bf6d21a08fb2))
* add MI300X multi-instance benchmarking plan ([9dd9435](https://github.com/OpenX-Inc/flow/commit/9dd9435d8d4b509fc3618f439b3623f4e8f00ad4))
* add publishing & distribution research (TikTok, YouTube, Instagram APIs) ([7e2d6a5](https://github.com/OpenX-Inc/flow/commit/7e2d6a5074a7c61c729936dec44f776b37ccd5b2))
* add system architecture design ([b601d30](https://github.com/OpenX-Inc/flow/commit/b601d302797b8050db72b1030262b8bb044b1aa5))
* add technology stack decisions ([2a96150](https://github.com/OpenX-Inc/flow/commit/2a961505115b3d74123a37d603e0d5e54ffebdc3))
* add video generation models research (Wan 2.2, HunyuanVideo, LTX, CogVideoX) ([4acc051](https://github.com/OpenX-Inc/flow/commit/4acc0517d90a6866952176e6873c00a78f64d9fe))
* rebrand to Flow with OpenX Flow tagline and comparison table ([7c3d7f0](https://github.com/OpenX-Inc/flow/commit/7c3d7f03d6f857ed6514fe9c68e7f9401e1dc9f2))
* update all documentation to reflect Flow branding and current features ([e0e1368](https://github.com/OpenX-Inc/flow/commit/e0e13682177db63d0a7e223f09cea08a7795704b))


### Miscellaneous Chores

* release 0.2.0 ([b3aff26](https://github.com/OpenX-Inc/flow/commit/b3aff26aecd70457152e20a56fb5cd7d35cec776))

## 0.1.0 (2026-06-12)


### Features

* add --dry-run mode to generate command (script only, no GPU) ([e0fa24b](https://github.com/OpenX-Inc/flow/commit/e0fa24bc1a76d7148772a8072f829eb7cca14b85))
* add autonomous scheduler with topic generation ([1b64f9b](https://github.com/OpenX-Inc/flow/commit/1b64f9b4cab8a5a453b48c899f50af1b49e8cfd2))
* add character bank for cross-scene and cross-video consistency ([0179c24](https://github.com/OpenX-Inc/flow/commit/0179c2430935519daff2fea358f4b236d547e41d))
* add core module scaffold (config, schemas, CLI entry point) ([41adc18](https://github.com/OpenX-Inc/flow/commit/41adc18d7aad64a84b453b45712aa842b75f617a))
* add DeepSeek and Ollama LLM provider support ([7fec793](https://github.com/OpenX-Inc/flow/commit/7fec79388ec936305582267236cc90be6f952131))
* add GPU backend client abstraction (Modal, RunPod, self-hosted) ([f228256](https://github.com/OpenX-Inc/flow/commit/f2282567514e4c66184e072be1b606af5a52f307))
* add GPU backend package scaffold ([4320b3b](https://github.com/OpenX-Inc/flow/commit/4320b3b8e85a62831eeeb69a8c28f43173c4e9d1))
* add keyframe generator for scene boundary images (Pass 1) ([22aaef3](https://github.com/OpenX-Inc/flow/commit/22aaef36d1d3885b100a69137fe227c043b02bac))
* add LLM-powered writer for script and shot list generation ([19f9a1a](https://github.com/OpenX-Inc/flow/commit/19f9a1aa042b5a260346464ef4e245866e8a7396))
* add MisoTTS 8B with one-shot voice cloning support ([0f0760e](https://github.com/OpenX-Inc/flow/commit/0f0760e11c020facc89a526ba9e327810ec2141a))
* add Modal deployment for Wan 2.2 GPU backend (A100 80GB) ([78dc023](https://github.com/OpenX-Inc/flow/commit/78dc023c1ff6ca1e2d2163fac427f35f7de34cdd))
* add parallel FLF2V generator for concurrent scene generation (Pass 2) ([1ad810e](https://github.com/OpenX-Inc/flow/commit/1ad810ecc31e17e0ba4671b79dc1c7a256f1911f))
* add pipeline orchestrator ([c01affc](https://github.com/OpenX-Inc/flow/commit/c01affc77d9036102dac5b4c1f0a75030b7bd840))
* add pipelined_flf2v mode (overlaps keyframe + video generation) ([e7946b0](https://github.com/OpenX-Inc/flow/commit/e7946b07799edcd9092aca41ce243162c7752187))
* add post-production (TTS, subtitles, FFmpeg assembly) ([c91cfee](https://github.com/OpenX-Inc/flow/commit/c91cfee4e6cee6b0c0f09e0e93fbfae682576382))
* add publisher module (TikTok, YouTube, Instagram stubs) ([8bb0d23](https://github.com/OpenX-Inc/flow/commit/8bb0d2379d924231155f1c04b888a4ecdb1ce956))
* add quality validation with retry on failed clip generation ([bded333](https://github.com/OpenX-Inc/flow/commit/bded33334322979e79ded4b4cfe26c53f93e7cb8))
* add standalone FastAPI GPU backend server (RunPod/self-hosted) ([36a465c](https://github.com/OpenX-Inc/flow/commit/36a465ccee06b25c54d242dbc9f2fd07c7c76bdb))
* add video generator with scene chaining (first-frame conditioning) ([e6039a0](https://github.com/OpenX-Inc/flow/commit/e6039a0b4ecf00177e47fb6eedcd2d7b625167be))
* add xDiT multi-GPU sequence parallelism for MI300X ([a29da98](https://github.com/OpenX-Inc/flow/commit/a29da980a188eebdc9053a1fb6a8e6017842f3fd))
* implement TikTok upload via Content Posting API ([af5dc38](https://github.com/OpenX-Inc/flow/commit/af5dc3855e17c5cd4b9af9ef6ac17d22f37c3346))
* implement YouTube Shorts upload with resumable upload protocol ([31de3d1](https://github.com/OpenX-Inc/flow/commit/31de3d1dccff86b72de0348003458d6d7219dd0b))
* integrate two-pass parallel generation into pipeline (generation_mode config) ([6feac98](https://github.com/OpenX-Inc/flow/commit/6feac98810cbdaabf3ebdb35155494ff992a54cb))


### Documentation

* add CI badge and dry-run usage to README ([3b2b796](https://github.com/OpenX-Inc/flow/commit/3b2b7963fea83fa6a590380acd48127aa2141980))
* add contributing guidelines ([c511ccf](https://github.com/OpenX-Inc/flow/commit/c511ccf5d134b14d2b5acfa1b706f4023ed30c6a))
* add cost projections for video generation at scale ([c4fdeff](https://github.com/OpenX-Inc/flow/commit/c4fdeffe5bf114ba87cc1c23f7b4734b921d092d))
* add example configuration file ([1c99b03](https://github.com/OpenX-Inc/flow/commit/1c99b03b2020b3be650e09ac3702e12e50803128))
* add Google Flow architecture analysis ([7c54b68](https://github.com/OpenX-Inc/flow/commit/7c54b6894c321819ee8201ced719b401788b2e49))
* add GPU infrastructure research (MI300X, A100, pricing, throughput) ([27417e0](https://github.com/OpenX-Inc/flow/commit/27417e0cb39d9db5d36fc0113405bf6d21a08fb2))
* add MI300X multi-instance benchmarking plan ([9dd9435](https://github.com/OpenX-Inc/flow/commit/9dd9435d8d4b509fc3618f439b3623f4e8f00ad4))
* add publishing & distribution research (TikTok, YouTube, Instagram APIs) ([7e2d6a5](https://github.com/OpenX-Inc/flow/commit/7e2d6a5074a7c61c729936dec44f776b37ccd5b2))
* add system architecture design ([b601d30](https://github.com/OpenX-Inc/flow/commit/b601d302797b8050db72b1030262b8bb044b1aa5))
* add technology stack decisions ([2a96150](https://github.com/OpenX-Inc/flow/commit/2a961505115b3d74123a37d603e0d5e54ffebdc3))
* add video generation models research (Wan 2.2, HunyuanVideo, LTX, CogVideoX) ([4acc051](https://github.com/OpenX-Inc/flow/commit/4acc0517d90a6866952176e6873c00a78f64d9fe))
* rebrand to Flow with OpenX Flow tagline and comparison table ([7c3d7f0](https://github.com/OpenX-Inc/flow/commit/7c3d7f03d6f857ed6514fe9c68e7f9401e1dc9f2))
* update all documentation to reflect Flow branding and current features ([e0e1368](https://github.com/OpenX-Inc/flow/commit/e0e13682177db63d0a7e223f09cea08a7795704b))

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
