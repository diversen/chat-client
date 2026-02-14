from chat_client.core import chat_service


class DummyOpenAIError(Exception):
    def __init__(self, message: str, body=None, response=None):
        super().__init__(message)
        self.body = body
        self.response = response


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_map_openai_error_message_for_image_modality_string():
    error = DummyOpenAIError("Image input modality is not enabled for models/gemma-3n-e4b-it")
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE


def test_map_openai_error_message_for_image_modality_in_body():
    error = DummyOpenAIError(
        "Error code: 400",
        body=[{"error": {"message": "Image input modality is not enabled for model"}}],
    )
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE


def test_map_openai_error_message_defaults_to_generic_message():
    error = DummyOpenAIError("Some unrelated provider error")
    assert chat_service.map_openai_error_message(error) == chat_service.GENERIC_OPENAI_ERROR_MESSAGE


def test_map_openai_error_message_for_image_modality_in_response_json():
    error = DummyOpenAIError(
        "Error code: 400",
        response=DummyResponse({"error": {"message": "Image input modality is not enabled"}}),
    )
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE
