from pydantic import BaseModel
from typing import List, Optional

class ChatMessageSchema(BaseModel):
    message: str

class ChatResponseSchema(BaseModel):
    ai_response: str
    has_updates: bool
    chat_history: List[dict]
