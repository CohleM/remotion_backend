# async_llm_client.py (Updated with post-processing)
import asyncio
import logging
from typing import Optional, Type, Any, List, Tuple
from openai import AsyncOpenAI, OpenAI
import httpx
import time
import os
from subtitle_generator.models import GroupDivision, SubtitleTimeline
from subtitle_generator.utils.post_processor import GroupPostProcessor  # NEW
from subtitle_generator.utils.hybrid_line_divider import HybridLineDivider, HybridPostProcessor

logger = logging.getLogger(__name__)


class AsyncLLMClient:
    """Async OpenAI client with proper timeouts and connection limits."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.1",
        max_concurrent: int = 3,
        max_retries: int = 3,
        timeout: float = 60.0
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

            print(messages)
            
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

    async def process_chunks_two_step(
        self,
        chunks: List[Any],
        config: Any,
    ) -> List[Tuple[int, Any, Any]]:
        """
        Two-step processing: first divide into groups, then format.
        Includes post-processing to enforce word limits.
        """
        logger.info(f"Starting TWO-STEP processing for {len(chunks)} chunks")
        
        # Initialize post-processor with config setting
        post_processor = GroupPostProcessor(max_words_per_group=config.max_words_per_group)
        
        # Step 1: Divide all chunks into groups concurrently
        logger.info("Step 1: Dividing chunks into groups...")
        group_divisions = await self._step1_divide_groups(chunks, config)
        
        # NEW: Post-process divisions to enforce word limits
        logger.info(f"Post-processing: Enforcing max {config.max_words_per_group} words per group...")
        processed_divisions = post_processor.process_divisions(group_divisions)
        
        # Log changes
        for i, (original, processed) in enumerate(zip(group_divisions, processed_divisions)):
            orig_count = len(original.groups)
            new_count = len(processed.groups)
            if orig_count != new_count:
                logger.info(
                    f"[Chunk {i}] Post-processing split {orig_count} groups "
                    f"into {new_count} groups"
                )
        
        # Step 2: Format all groups into final subtitle structure concurrently
        logger.info("Step 2: Formatting groups into subtitles...")
        formatted_timelines = await self._step2_format_groups(chunks, processed_divisions, config)
        
        # Combine results
        results = []
        for i, chunk in enumerate(chunks):
            results.append((i, chunk, formatted_timelines[i]))
        
        return results
    
    async def _step1_divide_groups(
        self, 
        chunks: List[Any], 
        config: Any
    ) -> List[GroupDivision]:
        """Step 1: Divide each chunk into verbatim groups."""
        tasks = []
        
        for chunk in chunks:
            user_prompt = f"""## VIDEO TRANSCRIPT SEGMENT (Chunk {chunk.chunk_index})
{chunk.text}

Divide this transcript into consecutive verbatim groups following the rules provided."""
            
            task = asyncio.create_task(
                self.generate(
                    system_prompt=config.group_division_prompt,
                    user_prompt=user_prompt,
                    response_format=config.group_division_format,
                    chunk_id=f"{chunk.chunk_index}-step1"
                ),
                name=f"chunk-{chunk.chunk_index}-step1"
            )
            tasks.append(task)
        
        # Wait for all group divisions to complete
        divisions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle errors
        results = []
        for i, result in enumerate(divisions):
            if isinstance(result, Exception):
                logger.error(f"[Chunk {i}] Step 1 failed: {result}")
                raise result
            results.append(result)
        
        return results
    
    async def _step2_format_groups(
        self,
        chunks: List[Any],
        group_divisions: List[GroupDivision],
        config: Any
    ) -> List[SubtitleTimeline]:
        """Step 2: Format pre-divided groups into final subtitle structure."""
        tasks = []
        
        for chunk, division in zip(chunks, group_divisions):
            # Prepare the groups for the formatting prompt
            groups_text = "\n".join([
                f"Group {i+1}: \"{group}\""
                for i, group in enumerate(division.groups)
            ])
            
            user_prompt = f"""## PRE-DIVIDED GROUPS (Chunk {chunk.chunk_index})
{groups_text}

Format these groups into the subtitle structure with proper line breaks and font types."""
            # print(config.system_prompt)

            task = asyncio.create_task(
                self.generate(
                    system_prompt=config.system_prompt,
                    user_prompt=user_prompt,
                    response_format=config.response_format,
                    chunk_id=f"{chunk.chunk_index}-step2"
                ),
                name=f"chunk-{chunk.chunk_index}-step2"
            )
            tasks.append(task)
        
        # Wait for all formatting to complete
        timelines = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle errors
        results = []
        for i, result in enumerate(timelines):
            if isinstance(result, Exception):
                logger.error(f"[Chunk {i}] Step 2 failed: {result}")
                raise result
            results.append(result)
        
        return results
    
    # Keep old method for backward compatibility
    async def process_chunks(
        self,
        chunks: List[Any],
        config: Any,
    ) -> List[Any]:
        """Original single-step processing (kept for compatibility)."""
        logger.info(f"Submitting {len(chunks)} chunks for processing (max {self.semaphore._value} concurrent)")
        
        task_to_meta = {}
        
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
        
        pending = set(task_to_meta.keys())
        results = []
        completed = 0
        
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED
            )
            
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
        
        results.sort(key=lambda x: x[0])
        return results
    
    async def close(self):
        """Cleanup resources."""
        await self.client.close()


    async def process_chunks_hybrid(
        self,
        chunks: List[Any],
        config: Any,
    ) -> List[Tuple[int, Any, Any]]:
        """
        Hybrid processing: LLM divides into groups+highlights, then rule-based line division.
        """
        logger.info(f"Starting HYBRID processing for {len(chunks)} chunks")
        
        # Initialize processors
        font_config = getattr(config, 'font_config', None)
        post_processor = HybridPostProcessor(max_words_per_group=config.max_words_per_group)
        # line_divider = HybridLineDivider(max_words_per_line=getattr(config, 'max_words_per_line', 3))
        line_divider = HybridLineDivider(
            max_words_per_line=getattr(config, 'max_words_per_line', 3),
            font_config=font_config
        )
        
        # Step 1: Divide all chunks into groups with highlights concurrently
        logger.info("Step 1: Dividing chunks into groups with highlights...")
        divisions_with_highlights = await self._step1_divide_groups_hybrid(chunks, config)

        print(' #########  ######### division  #########  #########  #########  ') 
        print(divisions_with_highlights) 
        print(' #########  ######### division #########  #########  #########  ')
        # Post-process: Split oversized groups and assign highlights correctly
        logger.info(f"Post-processing: Enforcing max {config.max_words_per_group} words per group...")
        processed_groups_per_chunk = post_processor.process_divisions(divisions_with_highlights)
        
        # Log changes
        for i, (original, processed) in enumerate(zip(divisions_with_highlights, processed_groups_per_chunk)):
            orig_count = len(original.groups)
            new_count = len(processed)
            if orig_count != new_count:
                logger.info(
                    f"[Chunk {i}] Post-processing split {orig_count} groups "
                    f"into {new_count} groups"
                )
        
        # Step 2: Rule-based line division (no LLM needed)
        logger.info("Step 2: Rule-based line division...")
        timelines = []
        for chunk_idx, chunk_groups in enumerate(processed_groups_per_chunk):
            subtitle_groups = line_divider.divide_groups(chunk_groups)
            timeline = SubtitleTimeline(timeline=subtitle_groups)
            timelines.append(timeline)
            logger.info(f"[Chunk {chunk_idx}] Divided into {len(subtitle_groups)} subtitle groups")
        
        # Combine results - match format of other methods
        results = []
        for i, chunk in enumerate(chunks):
            results.append((i, chunk, timelines[i]))
        
        return results

    async def _step1_divide_groups_hybrid(
        self, 
        chunks: List[Any], 
        config: Any
    ) -> List[Any]:  # List[GroupDivisionWithHighlights]
        """Step 1: Divide each chunk into groups with highlight words."""
        tasks = []
        
        for chunk in chunks:
            # Format prompt with max_words limit
            division_prompt = config.group_division_prompt
            
            user_prompt = f"""## VIDEO TRANSCRIPT SEGMENT (Chunk {chunk.chunk_index})
    {chunk.text}

    Divide this transcript into consecutive verbatim groups with highlight words following the rules provided."""
            
            task = asyncio.create_task(
                self.generate(
                    system_prompt=division_prompt,
                    user_prompt=user_prompt,
                    response_format=config.hybrid_division_format,
                    chunk_id=f"{chunk.chunk_index}-hybrid-step1"
                ),
                name=f"chunk-{chunk.chunk_index}-hybrid-step1"
            )
            tasks.append(task)
        
        # Wait for all group divisions to complete
        divisions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle errors
        results = []
        for i, result in enumerate(divisions):
            if isinstance(result, Exception):
                logger.error(f"[Chunk {i}] Hybrid Step 1 failed: {result}")
                raise result
            results.append(result)
        
        return results


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
            await asyncio.sleep(2 ** attempt)
    
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