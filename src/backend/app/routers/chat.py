"""Chat endpoint with SSE streaming.

POST /api/chat — accepts a user message and conversation_id,
streams the agent's response as Server-Sent Events.
"""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.auth import AuthenticatedUser
from app.models.conversation import Conversation, Message
from app.services.agent import run_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Rolling window size for conversation history sent to Claude
MAX_CONVERSATION_HISTORY = 30


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str = Field(..., min_length=1, max_length=4000, description="User's message")
    conversation_id: UUID | None = Field(
        default=None, description="Existing conversation ID, or null to start a new one"
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_class=StreamingResponse,
    responses={
        200: {"description": "SSE stream of agent response tokens"},
        401: {"description": "Not authenticated"},
        404: {"description": "Conversation not found or not owned by user"},
    },
)
async def chat(
    request: ChatRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Send a message and stream the agent's response via SSE.

    If conversation_id is null, a new conversation is created.
    The user message and final assistant response are persisted to DB.

    SSE event types:
    - meta: {"conversation_id": "..."} — sent first
    - token: {"text": "..."} — streamed text chunks
    - done: {"total_tokens": N} — signals completion
    - error: {"error": "..."} — on failure
    """
    conversation: Conversation | None = None

    # Resolve or create conversation
    if request.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == user.id,
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(user_id=user.id)
        db.add(conversation)
        await db.flush()  # Generate ID

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.flush()

    # Load conversation history (rolling window of last N messages for context)
    history_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(MAX_CONVERSATION_HISTORY + 1)  # +1 to account for the just-added user message
    )
    history_result = await db.execute(history_stmt)
    history_rows = list(reversed(history_result.scalars().all()))

    # Build Anthropic message format from history (exclude current message, it's passed separately)
    conversation_history: list[dict] = []
    for msg in history_rows[:-1]:  # Exclude the just-added user message
        conversation_history.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    conversation_id = conversation.id

    async def event_stream():
        """Generate SSE events."""
        # Send conversation metadata first
        yield _format_sse("meta", {"conversation_id": str(conversation_id)})

        full_response = []

        async for event in run_agent(
            user_message=request.message,
            conversation_history=conversation_history,
            db=db,
            settings=settings,
            user_id=user.id,
        ):
            yield _format_sse(event.event, json.loads(event.data))

            # Accumulate text for persistence
            if event.event == "token":
                token_data = json.loads(event.data)
                full_response.append(token_data.get("text", ""))

            # On done, save assistant message
            if event.event == "done":
                assistant_text = "".join(full_response)
                if assistant_text:
                    token_data = json.loads(event.data)
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_text,
                        token_count=token_data.get("total_tokens"),
                    )
                    db.add(assistant_msg)
                    await db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: str, data: dict) -> str:
    """Format a dict as an SSE message string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
