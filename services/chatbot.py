from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
from typing import List, Dict, Any  

load_dotenv()
os.getenv("OPENAI_API_KEY")

class ChatGPT():
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.system_prompt = """ You are an expert financial advisor chatbot. Your responsibilities include:
        - Analyzing market trends and stock performance
        - Providing investment strategies and portfolio advice
        - Explaining financial concepts and terminology
        - Offering risk assessment and management guidance
        - Discussing market news and impacts
        
        Keep responses clear, concise, and focused on actionable financial advice.
        """
    
    async def _get_response(self, user_message: str, chat_history: List[Dict[str, Any]]):
        try:
            messages = self._build_response(user_message=user_message, chat_history=chat_history)
            response = await self.client.chat.completions.create(
                temperature=0.5,
                model="gpt-4o",  
                max_tokens=500,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"There was a unexpected Error: {e}")
    
    def _build_response(self, user_message: str, chat_history: List[Dict[str, Any]] = None):
        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_history:
            messages.extend(chat_history)  
        messages.append({"role": "user", "content": user_message})
        return messages
