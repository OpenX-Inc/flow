"""Tests for configuration loading."""


from flow.config import Config, load_config


def test_default_config():
    config = Config()
    assert config.llm.provider == "openai"
    assert config.gpu_backend.provider == "modal"
    assert config.tts.provider == "edge"
    assert config.aspect_ratio == "9:16"


def test_load_missing_config():
    """Loading a nonexistent config returns defaults."""
    config = load_config("/nonexistent/path.toml")
    assert config.llm.provider == "openai"


def test_agent_config_env_overrides(monkeypatch):
    monkeypatch.setenv("FLOW_AGENT_PROVIDER", "openrouter")
    monkeypatch.setenv("FLOW_AGENT_MODEL", "moonshotai/kimi-k2.6")
    monkeypatch.setenv("FLOW_AGENT_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("FLOW_AGENT_API_KEY", "sk-or-v1-test")

    cfg = load_config("/nonexistent/path.toml")
    assert cfg.agent.provider == "openrouter"
    assert cfg.agent.model == "moonshotai/kimi-k2.6"
    assert cfg.agent.base_url == "https://openrouter.ai/api/v1"
    assert cfg.agent.api_key == "sk-or-v1-test"

