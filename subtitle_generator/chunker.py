
# --- chunker.py ---
from typing import List, Union, Dict, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


@dataclass
class TranscriptChunk:
    """Segment of transcript with absolute timestamps preserved"""
    text: str
    words: List[WordTimestamp]
    start: float  # Absolute start time in original audio
    end: float    # Absolute end time in original audio
    chunk_index: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "words": [asdict(w) for w in self.words],
            "start": self.start,
            "end": self.end,
            "chunk_index": self.chunk_index
        }


class TranscriptChunker:
    """Split long transcripts into <60s chunks while preserving absolute timestamps."""
    
    def __init__(self, max_duration: float = 55.0):  # Buffer under 60s
        self.max_duration = max_duration
    
    def chunk(self, transcript: Union[Dict, Any]) -> List[TranscriptChunk]:
        """
        Split transcript into chunks strictly less than max_duration.
        Preserves absolute timestamps from original audio.
        """
        words = self._extract_words(transcript)
        if not words:
            return []
        
        chunks = []
        current_words = []
        chunk_start = 0.0
        
        for word in words:
            if not current_words:
                chunk_start = word.start
            
            duration_if_added = word.end - chunk_start
            
            # If adding this word hits/exceeds limit, finalize current chunk
            if duration_if_added >= self.max_duration and current_words:
                chunks.append(self._create_chunk(current_words, chunk_start, len(chunks)))
                current_words = [word]
                chunk_start = word.start
            else:
                current_words.append(word)
        
        # Final chunk
        if current_words:
            chunks.append(self._create_chunk(current_words, chunk_start, len(chunks)))
        
        logger.info(f"Chunked transcript into {len(chunks)} segments (max {self.max_duration}s each)")
        return chunks
    
    def _extract_words(self, transcript: Union[Dict, Any]) -> List[WordTimestamp]:
        """Normalize various input formats to WordTimestamp objects."""
        if isinstance(transcript, dict):
            words_raw = transcript.get('words') or transcript.get('word_timestamps', [])
        else:
            words_raw = getattr(transcript, 'words', [])
        
        words = []
        for w in words_raw:
            if isinstance(w, dict):
                words.append(WordTimestamp(
                    word=w.get('word', ''),
                    start=w.get('start', 0.0),
                    end=w.get('end', 0.0)
                ))
            elif hasattr(w, 'word'):
                words.append(WordTimestamp(word=w.word, start=w.start, end=w.end))
        
        return words
    
    def _create_chunk(self, words: List[WordTimestamp], start: float, index: int) -> TranscriptChunk:
        """Create chunk from accumulated words."""
        text = " ".join(w.word for w in words)
        return TranscriptChunk(
            text=text,
            words=words,
            start=start,
            end=words[-1].end,
            chunk_index=index
        )
