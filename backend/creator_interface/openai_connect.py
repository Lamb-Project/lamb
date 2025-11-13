from openai import AsyncOpenAI, APIError
from fastapi import HTTPException
import os
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables
load_dotenv()

class OpenAIConnector:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_BASE_URL')
        )
        import config
        self.model = os.getenv('OPENAI_MODEL') or config.OPENAI_MODEL

    async def generate_assistant_description(self, assistant_data: Dict[str, Any]) -> str:
        """
        Generate a description for an assistant using the configured OpenAI model
        
        Args:
            assistant_data: Dictionary containing assistant configuration
            
        Returns:
            str: Generated description
            
        Raises:
            HTTPException: If the OpenAI service is unavailable or other errors occur
        """
        try:
            # Extract relevant information
            name = assistant_data.get("name", "")
            system_prompt = assistant_data.get("instructions", "")
            prompt_template = assistant_data.get("prompt_template", "")
            # Get metadata (prefer metadata field, fallback to api_callback for backward compatibility)
            metadata_str = assistant_data.get("metadata", assistant_data.get("api_callback", "{}"))
            
            # Parse metadata
            try:
                callback_data = json.loads(metadata_str)
                llm = callback_data.get("llm", "Not specified")
                rag_processor = callback_data.get("rag_processor", "Not specified")
            except json.JSONDecodeError:
                llm = "Not specified"
                rag_processor = "Not specified"
            
            # Construct the prompt
            prompt = f"""Generate a concise but informative description for an AI assistant with the following configuration:

Name: {name}
System Prompt: {system_prompt}
Prompt Template Structure: {prompt_template}

The description should:
- Match the language used in the prompt template
- Focus on the assistant's main purpose and unique characteristics
- Be professional and concise (under 200 characters)
- NOT mention RAG, knowledge bases, or specific LLM models
- NOT include technical implementation details
"""
            
            try:
                # Call OpenAI
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI that writes clear, concise assistant descriptions."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.7
                )
                
                # Extract and return the generated description
                return response.choices[0].message.content.strip()
                
            except APIError as e:
                logger.error(f"OpenAI API error: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"{self.model} service is currently unavailable. Please try again later or write your own description."
                )
                
        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Error generating assistant description: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating description: {str(e)}"
            ) 