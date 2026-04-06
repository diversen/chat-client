from pydantic import BaseModel, ConfigDict, Field


class UploadedImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data_url: str = ""
    attachment_id: int = 0
    name: str = ""
    content_type: str = ""
    size_bytes: int = 0


class UploadedAttachmentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    attachment_id: int
    name: str = ""
    content_type: str = ""
    size_bytes: int = 0


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    content: str = ""
    images: list[UploadedImageRequest] = Field(default_factory=list)
    attachments: list[UploadedAttachmentRequest] = Field(default_factory=list)


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str
    dialog_id: str = ""
    messages: list[ChatMessageRequest] = Field(default_factory=list)


class CreateDialogRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    initial_message: str = ""


class CreateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    content: str
    model: str = ""
    images: list[UploadedImageRequest] = Field(default_factory=list)
    attachments: list[UploadedAttachmentRequest] = Field(default_factory=list)


class UpdateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str


class AssistantTurnEventItemRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_type: str
    reasoning_text: str = ""
    content_text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    arguments_json: str = "{}"
    result_text: str = ""
    error_text: str = ""


class CreateAssistantTurnEventsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    turn_id: str
    events: list[AssistantTurnEventItemRequest] = Field(default_factory=list)
