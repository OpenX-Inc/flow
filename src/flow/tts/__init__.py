"""Text-to-speech providers.

Select a provider via config (``[tts] provider = "edge" | "miso"``) and obtain
an instance with :func:`get_tts_provider`. Third parties can add backends with
:func:`register_provider` without modifying Flow::

    from flow.tts import register_provider, TTSProvider

    @register_provider
    class MyProvider(TTSProvider):
        name = "myprovider"
        def synthesize(self, text, output_path, **kw):
            ...
"""

from __future__ import annotations

from flow.config import TTSConfig
from flow.tts.base import TTSProvider
from flow.tts.edge import EdgeTTSProvider
from flow.tts.miso import MisoTTSProvider

_REGISTRY: dict[str, type[TTSProvider]] = {}


def register_provider(cls: type[TTSProvider]) -> type[TTSProvider]:
    """Register a provider class (usable as a decorator). Keyed by ``cls.name``."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must set a non-empty `name`")
    _REGISTRY[cls.name] = cls
    return cls


def available_providers() -> list[str]:
    """Sorted list of registered provider names."""
    return sorted(_REGISTRY)


def get_tts_provider(config: TTSConfig, *, gpu_backend_url: str = "") -> TTSProvider:
    """Construct the provider selected by ``config.provider``."""
    cls = _REGISTRY.get(config.provider)
    if cls is None:
        raise ValueError(
            f"Unknown TTS provider {config.provider!r}. "
            f"Available: {', '.join(available_providers()) or '(none)'}"
        )
    return cls(config, gpu_backend_url=gpu_backend_url)


# Register built-in providers.
register_provider(EdgeTTSProvider)
register_provider(MisoTTSProvider)

__all__ = [
    "TTSProvider",
    "EdgeTTSProvider",
    "MisoTTSProvider",
    "get_tts_provider",
    "register_provider",
    "available_providers",
]
