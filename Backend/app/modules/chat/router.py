from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.modules.chat.schemas import ChatMessageSchema
from app.modules.chat.service import chat_service

router = APIRouter(prefix="/api/chat", tags=["AI Chat"])

@router.post("/{session_id}")
async def post_chat_message(
    session_id: str,
    payload: ChatMessageSchema,
    current_user: dict = Depends(get_current_user)
):
    """
    Sends a chat instruction to the AI Swarm Copilot.
    """
    result = await chat_service.process_chat(session_id, current_user["id"], payload)
    return result
