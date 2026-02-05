# async_llm_client.py (Fixed)
import asyncio
import logging
from typing import Optional, Type, Any, List
from openai import AsyncOpenAI,OpenAI
import httpx
import time
import os

logger = logging.getLogger(__name__)


class AsyncLLMClient:
    """Async OpenAI client with proper timeouts and connection limits."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.1",
        max_concurrent: int = 3,  # Reduced default to avoid rate limits
        max_retries: int = 3,
        timeout: float = 60.0  # Add explicit timeout
    ):
        self.model = model
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout
        
        # Configure httpx client with limits and timeouts
        limits = httpx.Limits(
            max_connections=max_concurrent + 2,
            max_keepalive_connections=max_concurrent
        )
        
        timeout_config = httpx.Timeout(
            timeout,
            connect=10.0,
            read=timeout,
            write=10.0,
            pool=10.0
        )
        
        http_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout_config
        )
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            http_client=http_client,
            timeout=timeout
        )
    
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Type[Any]] = None,
        chunk_id: Optional[int] = None
    ) -> Any:
        """Generate with semaphore control and proper error handling."""
        async with self.semaphore:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            start_time = time.time()
            logger.info(f"[Chunk {chunk_id}] Starting API call...")
            
            for attempt in range(self.max_retries):
                try:
                    if response_format:
                        completion = await self.client.chat.completions.parse(
                            model=self.model,
                            messages=messages,
                            response_format=response_format,
                        )
                        result = completion.choices[0].message.parsed
                    else:
                        completion = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages
                        )
                        result = completion.choices[0].message.content
                    
                    elapsed = time.time() - start_time
                    logger.info(f"[Chunk {chunk_id}] Completed in {elapsed:.1f}s")
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error(f"[Chunk {chunk_id}] Timeout after {self.timeout}s")
                    raise
                except Exception as e:
                    wait_time = min(30, (2 ** attempt) + (hash(chunk_id) % 10) / 10)
                    logger.warning(
                        f"[Chunk {chunk_id}] Attempt {attempt + 1} failed: {e}, "
                        f"retrying in {wait_time:.1f}s..."
                    )
                    
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"[Chunk {chunk_id}] All retries exhausted")
                        raise e
    async def process_chunks(
        self,
        chunks: List[Any],
        config: Any,
    ) -> List[Any]:
        """Process chunks with progress tracking."""
        logger.info(f"Submitting {len(chunks)} chunks for processing (max {self.semaphore._value} concurrent)")
        
        # Create tasks and map them to chunk metadata
        task_to_meta = {}  # task -> (chunk_index, chunk)
        
        for chunk in chunks:
            user_prompt = f"""## VIDEO TRANSCRIPT (Segment {chunk.chunk_index})
{chunk.text}

Analyze this transcript segment and create optimized subtitle groups. 
Note: This is segment {chunk.chunk_index} of a longer video (starts at {chunk.start:.1f}s)."""
            
            task = asyncio.create_task(
                self.generate(
                    system_prompt=config.system_prompt,
                    user_prompt=user_prompt,
                    response_format=config.response_format,
                    chunk_id=chunk.chunk_index
                ),
                name=f"chunk-{chunk.chunk_index}"
            )
            task_to_meta[task] = (chunk.chunk_index, chunk)
        
        # Process with progress tracking
        pending = set(task_to_meta.keys())
        results = []
        completed = 0
        
        while pending:
            # Wait for next batch to complete
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Handle completed tasks
            for task in done:
                chunk_idx, chunk = task_to_meta[task]
                try:
                    result = task.result()
                    results.append((chunk_idx, chunk, result))
                    completed += 1
                    logger.info(f"Progress: {completed}/{len(chunks)} chunks completed")
                except Exception as e:
                    logger.error(f"[Chunk {chunk_idx}] Task failed: {e}")
                    raise
        
        # Sort by chunk index to maintain order
        results.sort(key=lambda x: x[0])
        return results
    
    async def close(self):
        """Cleanup resources."""
        await self.client.close()



async def get_transcript_async(audio_path: str, retries: int = 3) -> dict:
    """
    Async version of get_transcript using AsyncOpenAI client.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    client = AsyncOpenAI(api_key=api_key)
    
    for attempt in range(retries):
        try:
            with open(audio_path, "rb") as f:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["word"]
                )
            return transcript.model_dump()
            
        except Exception as e:
            print(f"[TRANSCRIBE] Attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("All retry attempts failed")


# Keep sync version for backward compatibility
def get_transcript(audio_path: str, retries: int = 3) -> dict:
    """Synchronous version (for non-async contexts)."""
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    for attempt in range(retries):
        try:
            with open(audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="verbose_verbose",
                    timestamp_granularities=["word"]
                )
            return transcript.model_dump()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)