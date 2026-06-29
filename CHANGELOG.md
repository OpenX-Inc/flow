# Changelog

## [0.4.0](https://github.com/OpenX-Inc/flow/compare/v0.3.0...v0.4.0) (2026-06-29)


### Features

* **tts:** add pluggable TTSProvider interface ([971111e](https://github.com/OpenX-Inc/flow/commit/971111e1478ca762fdc341a1a530d59da7482baf))
* **tts:** add TTSConfig.miso_endpoint for a dedicated MisoTTS endpoint ([a41c56d](https://github.com/OpenX-Inc/flow/commit/a41c56df4757082014c1c0a65fdfb8bdc179a56f))
* **tts:** EdgeTTSProvider (free Microsoft voices, no cloning) ([ce44371](https://github.com/OpenX-Inc/flow/commit/ce44371fd5ec134fe5f9553f11c3c89a5d831e0a))
* **tts:** MisoTTSProvider (voice cloning; local GPU or HTTP endpoint) ([77e1614](https://github.com/OpenX-Inc/flow/commit/77e161473a5877dd5da53d0eba0c815200864858))
* **tts:** pluggable TTS providers + voice cloning ([dfd6964](https://github.com/OpenX-Inc/flow/commit/dfd69640a309609d1807be2812f21804c9f4e7e7))
* **tts:** provider registry — get_tts_provider/register_provider/available_providers ([92573c5](https://github.com/OpenX-Inc/flow/commit/92573c5986aeab7d5d79ab22844621bdbf56542e))


### Documentation

* **tts:** document miso_endpoint + provider options in config.example.toml ([023a336](https://github.com/OpenX-Inc/flow/commit/023a3368a5f42aa228246e3f438020e272c6ce5d))
* **tts:** README section on the pluggable TTS layer + voice cloning + custom providers ([fbbf486](https://github.com/OpenX-Inc/flow/commit/fbbf4860aacde5b91d122d20655627ed6041ce1f))

## [0.3.0](https://github.com/OpenX-Inc/flow/compare/v0.2.0...v0.3.0) (2026-06-28)


### Features

* 0.3 agentic video-editing layer (41 MCP tools + kimi agent) ([9dc2dcb](https://github.com/OpenX-Inc/flow/commit/9dc2dcbb04c87c1b40ea9db110c50efca37be127))
* **agent:** add run_stream() generator for SSE; run() consumes it ([16fd291](https://github.com/OpenX-Inc/flow/commit/16fd291679d520ee71352fc5cb85af94c47d2463))
* **agent:** NVIDIA build client (OpenAI-compatible, default kimi=moonshotai/kimi-k2.6) ([35fe3ee](https://github.com/OpenX-Inc/flow/commit/35fe3ee7b07c12b9887855b23868dc661c8ee38b))
* **agent:** real GenerationService (Modal video + edge-tts narration) ([82f2907](https://github.com/OpenX-Inc/flow/commit/82f290728fde00a7ae026207b24ab56380e0c067))
* **agent:** tool-calling loop (kimi drives the 41 tools end-to-end) ([89a621e](https://github.com/OpenX-Inc/flow/commit/89a621ea82744b7ae1e028fd1f465307a3e7d52c))
* **agent:** wire generation tools to real execution (background jobs) ([a0e9219](https://github.com/OpenX-Inc/flow/commit/a0e921946ea41e367a7b6a2c0de5ef376bcd02b6))
* **api:** agent HTTP API — /agent/chat (SSE), /agent/models, /agent/undo ([43494f4](https://github.com/OpenX-Inc/flow/commit/43494f4b2ad41be386b475353f868748da8988ed))
* **cli:** add 'flow agent' and 'flow mcp' commands ([e236baa](https://github.com/OpenX-Inc/flow/commit/e236baa00f909b3375367c110b00f8f06bdfc25e))
* **config:** add [agent], [mcp], [billing] config sections ([41901f0](https://github.com/OpenX-Inc/flow/commit/41901f021f023e2c93181c532a8a4537c482702a))
* **mcp:** streamable-HTTP MCP server exposing all 41 tools ([65d00a5](https://github.com/OpenX-Inc/flow/commit/65d00a5f7dc7bacaba6b8f50b4e020d712aa04a0))
* **store:** audio + text Track/TrackItem models (narration, music, captions) ([d982ca1](https://github.com/OpenX-Inc/flow/commit/d982ca1a7324334bbb883d1956a84f6a64e23c92))
* **store:** Clip + Keyframe + Transform models (scene as video-track element) ([1daa4b3](https://github.com/OpenX-Inc/flow/commit/1daa4b305294af38564ecb46b74c5812dbbb3a49))
* **store:** Clip gains ColorGrade + Effect (color/FX support) ([fcd3e97](https://github.com/OpenX-Inc/flow/commit/fcd3e97c41244c5796c6ae3761427ce5d26a1154))
* **store:** frame math helpers (frames as authoritative time unit) ([0d99ca8](https://github.com/OpenX-Inc/flow/commit/0d99ca89d7ec6fcd44a6e216f5561df775da5dad))
* **store:** import_shotlist shim (pipeline ShotList -&gt; timeline Project) ([b331e54](https://github.com/OpenX-Inc/flow/commit/b331e54cfeb31896df6d516550166bad5f92a51c))
* **store:** JSON-backed ProjectStore (atomic save/load/list/delete) ([431b665](https://github.com/OpenX-Inc/flow/commit/431b665ea8ae7c0c5e063f5c636e2a335bdc49ec))
* **store:** make ProjectStore DB-backed (replaces JSON-file store) ([6ffa121](https://github.com/OpenX-Inc/flow/commit/6ffa1213be5bd9e3cdc6d206f91ca071895b146a))
* **store:** MediaAsset + Folder models (library with provenance + reverse index) ([9dcc07f](https://github.com/OpenX-Inc/flow/commit/9dcc07f54697d455300668438c7cbcee94789986))
* **store:** Project aggregate (video track + tracks + media + cast + undo) ([736979a](https://github.com/OpenX-Inc/flow/commit/736979adb53ce4bc064142053a4c90a8738ac0db))
* **store:** SQLModel engine + projects table (SQLite default, Postgres via env) ([46f3277](https://github.com/OpenX-Inc/flow/commit/46f3277de1f19f6cc99dfc6b7988b0c37ff28d66))
* **store:** UndoEntry model (LIFO reversible-edit record) ([794be86](https://github.com/OpenX-Inc/flow/commit/794be864fb9283808afaca230f415146065c40c5))
* **tools:** advanced timeline tools (keyframes, move, insert, ripple-delete, remove_track) ([4d0ebe3](https://github.com/OpenX-Inc/flow/commit/4d0ebe39258bf83ad18eab01330973e4337367ad))
* **tools:** analysis-read tools from store (get_transcript, inspect_timeline, inspect_media, search_media) ([3941179](https://github.com/OpenX-Inc/flow/commit/3941179622bcf74e87ba28e55c3284c13ad51538))
* **tools:** central tool loader (register all tools on one import) ([73a128e](https://github.com/OpenX-Inc/flow/commit/73a128e4c7329c374c56d690cc66c3ad7c2b373b))
* **tools:** clip-editing tools (set_clip_properties, split_clip) ([acaeaf9](https://github.com/OpenX-Inc/flow/commit/acaeaf95d407ff21e8ad9cc1a0478f728cf1b51a))
* **tools:** color/FX tools (apply_color, apply_effect, inspect_color) ([fe5c98e](https://github.com/OpenX-Inc/flow/commit/fe5c98ebf912ee929f8cf12f2f0ec1627ad437ec))
* **tools:** context/read tools (get_project, get_media, list_characters, list_models) ([f966b49](https://github.com/OpenX-Inc/flow/commit/f966b49e8526f9cb041aa7288a1b63a06ae36f3b))
* **tools:** Flow-native tools (cast, narration, plan_video, clone_voice, start_generation) ([a698705](https://github.com/OpenX-Inc/flow/commit/a698705cf3ae70b336ef1ad96e7770d9f91089de))
* **tools:** generation tools (generate_video/image/audio, upscale, import) ([d8d0705](https://github.com/OpenX-Inc/flow/commit/d8d07056db619c09e432c25dd028dcc4b2b1bd56))
* **tools:** media-management tools (folders + library, reference-aware soft delete) ([f5ec89b](https://github.com/OpenX-Inc/flow/commit/f5ec89b1df77bbd4e2aff5331473cd2e1cd43794))
* **tools:** register advanced timeline tools in the loader ([7b61b36](https://github.com/OpenX-Inc/flow/commit/7b61b36ae9a65fff615519e0d8266052154866c9))
* **tools:** register analysis-read tools in the loader ([75b942b](https://github.com/OpenX-Inc/flow/commit/75b942bbbdac88da3036817847ff024842e50908))
* **tools:** register Flow-native tools in the loader ([5743ffc](https://github.com/OpenX-Inc/flow/commit/5743ffc26d5d9e9cd947106eaa1656a0f8e3754c))
* **tools:** register generation tools in the loader ([eb57be2](https://github.com/OpenX-Inc/flow/commit/eb57be2d8fb3471da862fbf241394a7466344259))
* **tools:** register media-management tools in the loader ([fafdf54](https://github.com/OpenX-Inc/flow/commit/fafdf543304bfcb63aa6cc17cfb121fe2c2cbc27))
* **tools:** register text + color tools in the loader ([601c09e](https://github.com/OpenX-Inc/flow/commit/601c09e0d9dba4c4bc29e2cc538f9f38200a901d))
* **tools:** result envelope + dispatch chokepoint with guardrails ([54a842d](https://github.com/OpenX-Inc/flow/commit/54a842de6dc7b5e2ce78dc1a6e91610f64e1f6ac))
* **tools:** scene-management tools (create/update/delete/reorder scenes) ([c5f3ba9](https://github.com/OpenX-Inc/flow/commit/c5f3ba904c7734df664ca19b9a091e159a53450d))
* **tools:** text tools (add_texts titles, add_captions from narration) ([9248b35](https://github.com/OpenX-Inc/flow/commit/9248b35de5b64bb494dfcf041e72a69b3ef85ed1))
* **tools:** tool registry — [@tool](https://github.com/tool) decorator + param DSL -&gt; JSON/OpenAI/MCP schema ([19837dc](https://github.com/OpenX-Inc/flow/commit/19837dc6432e1b72d1e911a1a44ca919bdf6548b))
* **tools:** undo tool (pop LIFO + restore snapshot) ([a69b5bc](https://github.com/OpenX-Inc/flow/commit/a69b5bc8b969edf4ea4dfdc9089250405af47cf3))


### Bug Fixes

* **imports:** use 'flow' package imports, not 'src.flow' ([cbccfb3](https://github.com/OpenX-Inc/flow/commit/cbccfb3a781c37873afb8e248d935466cf5dda34))


### Documentation

* **0.3:** deep spec — color/FX + media-management tools (ffmpeg filtergraph compiler) ([021bb3e](https://github.com/OpenX-Inc/flow/commit/021bb3e448139d1ae389821b887804f93d0d6a2e))
* **0.3:** deep spec — context/read tools (get_project, inspect_media, get_transcript, ...) ([33bbaba](https://github.com/OpenX-Inc/flow/commit/33bbabab5899813a1cb2b5b24bb9bf4fc5d7deb5))
* **0.3:** deep spec — Flow-native tools (characters, plan_video orchestrator, voice clone) ([51e7a9c](https://github.com/OpenX-Inc/flow/commit/51e7a9ca21a91c7350f134a7d2f0deb17eef3c48))
* **0.3:** deep spec — runtime (VPS MCP server + nanocode-style agent loop, kimi via NVIDIA build) ([3a234bd](https://github.com/OpenX-Inc/flow/commit/3a234bd627756452236417475bbf80c5ae3d0eed))
* **0.3:** deep spec — text + generation tools (captions, Wan2.2/VACE, TTS/voice) ([1a32656](https://github.com/OpenX-Inc/flow/commit/1a32656e4dfb222b865577ebb82d5d9a68f1771a))
* **0.3:** deep spec — timeline-edit tools (move/split/ripple/keyframes on scenes-as-clips) ([f6f866d](https://github.com/OpenX-Inc/flow/commit/f6f866d7084e6b2f9fb2ffe7b9ce670020fae087))
* **config:** document [agent]/[mcp]/[billing] in config.example.toml ([83140e8](https://github.com/OpenX-Inc/flow/commit/83140e82c3e23183bded189953b9f88b8b17bd45))
* **readme:** add Agentic Editing (0.3) section + roadmap entry ([26aac7c](https://github.com/OpenX-Inc/flow/commit/26aac7cff7836705630ca13869919b2f3717984a))
* **research:** analyze Palmier Pro + agentic video editing landscape ([959fbf9](https://github.com/OpenX-Inc/flow/commit/959fbf92697a528f74e403f6f244162bc40daeec))
* **research:** catalog Palmier's 35 video tools + map to Flow scene tools ([8cf51ed](https://github.com/OpenX-Inc/flow/commit/8cf51ed1755d61178b704500e0c2975e94bd4506))
* **research:** refine after Palmier code teardown — MCP-on-VPS is the fit ([13b8738](https://github.com/OpenX-Inc/flow/commit/13b8738215a64d1beb7a5a3b97e70202695ec44a))
* **research:** scope 0.3 to ALL 35 tools; scenes ARE the timeline ([3c32906](https://github.com/OpenX-Inc/flow/commit/3c32906b098996b17873edcb21642c8b6a3da159))
* **research:** teardown nanocode's agent tool-loop ([ba0cd56](https://github.com/OpenX-Inc/flow/commit/ba0cd5682a4f79d109fdf057e012c4dfe0c8e953))

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
