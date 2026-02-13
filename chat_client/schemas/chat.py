from pydantic import BaseModel, ConfigDict, Field


class UploadedImageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data_url: str


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    content: str = ""
    images: list[UploadedImageRequest] = Field(default_factory=list)


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str
    messages: list[ChatMessageRequest] = Field(default_factory=list)


class CreateDialogRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str


class CreateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    content: str


class UpdateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str

