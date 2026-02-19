# subtitle_generator/transcript_modification.py
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

# Update subtitle_generator/transcript_modification.py

async def apply_styles(raw_data, style):
    """Async version - call with await"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("API key required via --api-key or OPENAI_API_KEY env var")
    
    from subtitle_generator.config import PromptRegistry
    from subtitle_generator.pipeline import SubtitlePipeline
    
    config = PromptRegistry.get_config(style)
    pipeline = SubtitlePipeline(
        api_key=api_key,
        model=config.model,
        max_chunk_duration=config.max_chunk,
        max_concurrent=config.max_concurrent,
        use_hybrid=config.use_hybrid  # Pass through
    )
    
    # Call pipeline.run directly (already async)
    result = await pipeline.run(
        raw_data=raw_data,
        config=config
    )
    
    print(f"✅ Processed {len(result)} subtitle groups -> {result}")
    print(f"   Total duration: {result[-1]['end']:.1f}s" if result else "   Empty result")
    
    return result

