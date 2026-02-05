# pipeline.py (Updated cleanup)
import asyncio
import logging
from typing import List, Optional
from .merger import TimelineMerger
from .chunker import TranscriptChunker
from .async_llm_client import AsyncLLMClient
from .timestamp_matcher import TimestampMatcher
from .io_handler import IOHandler
from .config import GenerationConfig

logger = logging.getLogger(__name__)


class SubtitlePipeline:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_chunk_duration: float = 55.0,
        max_concurrent: int = 3,  # Conservative default
        timeout: float = 60.0,
        matcher: Optional[TimestampMatcher] = None,
        io_handler: Optional[IOHandler] = None
    ):
        self.chunker = TranscriptChunker(max_duration=max_chunk_duration)
        self.llm_client = AsyncLLMClient(
            api_key=api_key,
            model=model,
            max_concurrent=max_concurrent,
            timeout=timeout
        )
        self.matcher = matcher or TimestampMatcher()
        self.io = io_handler or IOHandler()
        self.merger = TimelineMerger()
        self.model = model
    
    async def process_chunk(self, chunk, timeline):
        """Process single chunk."""
        groups = [g.model_dump() for g in timeline.timeline]
        
        from .models import WordTimestamp
        word_ts = [WordTimestamp(w.word, w.start, w.end) for w in chunk.words]
        
        processed = self.matcher.process_groups(groups, word_ts)
        return [g.model_dump() for g in processed]
    
    async def run(
        self,
        raw_data: dict,
        # output_path: str,
        config: GenerationConfig,
        transcript_override: Optional[str] = None
    ) -> List[dict]:
        """Run with proper resource management."""
        try:
            # Load and chunk
            # raw_data = self.io.load_pickle(pickle_path)
            chunks = self.chunker.chunk(raw_data)
            
            if not chunks:
                raise ValueError("No chunks generated")
            
            logger.info(f"Processing {len(chunks)} chunks...")
            
            # Generate timelines
            chunk_results = await self.llm_client.process_chunks(chunks, config)
            
            # Process timestamps
            processed_chunks = []
            for chunk_idx, chunk, timeline in chunk_results:
                processed = await self.process_chunk(chunk, timeline)
                processed_chunks.append(processed)
            
            # Merge
            final_data = self.merger.merge(processed_chunks)
            
            if not self.merger.validate_continuity(final_data):
                logger.warning("Timeline continuity issues detected")
            
            # self.io.save_json(final_data, output_path)
            return final_data
            
        finally:
            # Ensure cleanup
            await self.llm_client.close()
    
    def run_sync(self, *args, **kwargs):
        """Sync wrapper."""
        return asyncio.run(self.run(*args, **kwargs))