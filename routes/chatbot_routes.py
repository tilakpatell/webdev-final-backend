from fastapi import APIRouter, HTTPException
from services.chatbot import ChatGPT
from schemas import ChatRequest

router = APIRouter()
chatgpt = ChatGPT()

@router.post("/chat")
async def chatgpt_post(chat_data: ChatRequest):
  try:
    response = chatgpt._get_response(
      user_message=chat_data.message,
      chat_history=chat_data.chat_history
    )
    return {"response": response}
  except Exception as e:
    raise HTTPException(status_code="500", detail=str(e))
    
  


