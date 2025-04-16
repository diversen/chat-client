from openai import OpenAI


def get_provider_models(provider: dict):
    """
    Helper to get all ollama models
    """
    client = OpenAI(**provider)
    ollama_model_names = []
    ollama_models = client.models.list()
    for model in ollama_models:
        model_name = model.id
        ollama_model_names.append(model_name)

    ollama_model_names.sort()
    return ollama_model_names
