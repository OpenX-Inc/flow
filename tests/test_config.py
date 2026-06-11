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
