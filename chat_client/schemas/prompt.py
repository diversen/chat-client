from pydantic import BaseModel, ConfigDict


class PromptUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    prompt: str
