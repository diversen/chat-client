import logging

from chat_client.core.api_utils import get_provider_models

logger: logging.Logger = logging.getLogger(__name__)


def resolve_models(configured_models: dict | None, providers: dict | None) -> dict:
    """
    Return configured models plus any provider-backed dynamic models.
    """
    resolved_models = dict(configured_models) if isinstance(configured_models, dict) else {}
    configured_providers = providers if isinstance(providers, dict) else {}

    ollama_provider = configured_providers.get("ollama")
    if not isinstance(ollama_provider, dict):
        return resolved_models

    try:
        ollama_models = get_provider_models(ollama_provider)
    except Exception as exc:
        logger.warning("Unable to load Ollama models from provider config: %s", exc)
        return resolved_models

    for model_name in ollama_models:
        resolved_models[model_name] = "ollama"

    return resolved_models
