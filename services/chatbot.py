from anthropic import AsyncAnthropic
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from fastapi import HTTPException
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class ChatGPT:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        print(api_key)
        if not api_key:
            logger.error("Anthropic API key not found in environment variables")
            raise ValueError("Anthropic API key not configured")
            
        self.client = AsyncAnthropic(api_key=api_key)
        self.system_prompt = """You are an expert financial advisor chatbot. Your responsibilities include:
        - Analyzing market trends and stock performance
        - Providing investment strategies and portfolio advice
        - Explaining financial concepts and terminology
        - Offering risk assessment and management guidance
        - Discussing market news and impacts
        - Explanations of various stock and companies
        
        Provide clear, concise responses with specific recommendations when appropriate.
        Format your responses with clear sections and bullet points for readability.
        Always consider risk factors and include relevant disclaimers when giving financial advice.
        """
    
    async def _get_response(self, user_message: str, chat_history: List[Dict[str, Any]] | None = None) -> str:
        try:
            logger.info(f"Generating response for message: {user_message[:100]}...")  # Log first 100 chars
            
            # Build the complete message with system prompt, chat history, and user message
            complete_message = self._build_message(user_message, chat_history)
            logger.info("Built message structure")
            
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": complete_message
                }]
            )
            
            if not response.content:
                logger.error("No content in response from Claude")
                raise ValueError("No response generated from Claude")
                
            content = response.content[0].text
            logger.info(f"Successfully generated response of length {len(content)}")
            
            return content
            
        except Exception as e:
            logger.error(f"Error in _get_response: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate analysis: {str(e)}"
            )
    
    def _build_message(self, user_message: str, chat_history: List[Dict[str, Any]] | None = None) -> str:
        try:
            # Start with the system prompt
            complete_message = self.system_prompt + "\n\n"
            
            # Add chat history if provided
            if chat_history:
                # Only keep last 5 messages to maintain context without exceeding limits
                for msg in chat_history[-5:]:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        role = "Human:" if msg["role"] == "user" else "Assistant:"
                        complete_message += f"{role} {msg['content']}\n\n"
            
            # Add the current user message
            complete_message += f"Human: {user_message}\n\nAssistant:"
            return complete_message
            
        except Exception as e:
            logger.error(f"Error building message: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error building message structure: {str(e)}"
            )
