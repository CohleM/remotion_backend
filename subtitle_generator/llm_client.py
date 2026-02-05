
# --- llm_client.py ---
import time
import logging
from typing import Optional, Type, Any, List
from openai import OpenAI
from models import WordTimestamp


class LLMClient:
    """Wrapper for OpenAI API with retry logic and structured output."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Type[Any]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Any:
        """
        Generate completion with automatic retry and structured output support.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if response_format:
                    completion = self.client.chat.completions.parse(
                        model=self.model,
                        messages=messages,
                        response_format=response_format,
                    )
                    return completion.choices[0].message.parsed
                else:
                    completion = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages
                    )
                    return completion.choices[0].message.content
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    time.sleep(sleep_time)
                continue
        
        logger.error(f"All {max_retries} retry attempts failed")
        raise last_exception




def get_transcript(audio_path: str, retries: int = 3) -> List[WordTimestamp]:
    
    """Get word timestamps with retry logic."""
    for attempt in range(retries):
        try:
            with open(audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )
            return transcript
        except Exception as e:
            if attempt == retries - 1: raise
            time.sleep(2 ** attempt)