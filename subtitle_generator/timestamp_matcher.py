
# --- timestamp_matcher.py ---
import re
import logging
from typing import List, Tuple, Optional
from subtitle_generator.models import WordTimestamp, ProcessedGroup, ProcessedLine

logger = logging.getLogger(__name__)


class TimestampMatcher:
    """Aligns generated subtitle groups with original word timestamps."""
    
    @staticmethod
    def normalize_word(word: str) -> str:
        """Remove punctuation and normalize for matching."""
        return re.sub(r'[^\w\s]', '', word.lower()).strip()
    
    def find_phrase_timestamp(
        self, 
        phrase: str, 
        word_timestamps: List[WordTimestamp],
        search_start: Optional[float] = None,
        search_end: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Find start and end timestamps for a phrase within optional time bounds.
        """
        phrase_words = [
            self.normalize_word(w) 
            for w in re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", phrase)
            if self.normalize_word(w)
        ]
        
        if not phrase_words:
            return (0.0, 0.0)
        
        transcript_words = [self.normalize_word(w.word) for w in word_timestamps]
        
        for i in range(len(transcript_words) - len(phrase_words) + 1):
            if transcript_words[i:i+len(phrase_words)] == phrase_words:
                start_time = word_timestamps[i].start
                end_time = word_timestamps[i + len(phrase_words) - 1].end
                
                # Check bounds if specified
                if search_start is not None and start_time < search_start:
                    continue
                if search_end is not None and end_time > search_end:
                    continue
                    
                return (start_time, end_time)
        
        return (0.0, 0.0)
    
    def get_word_timestamps(
        self, 
        line_text: str, 
        word_timestamps: List[WordTimestamp],
        line_start: float,
        line_end: float
    ) -> List[dict]:
        """Get individual word timestamps for a line."""
        line_words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", line_text)
        normalized_line_words = [self.normalize_word(w) for w in line_words]
        transcript_words = [self.normalize_word(w.word) for w in word_timestamps]
        
        word_details = []
        
        for i in range(len(transcript_words) - len(normalized_line_words) + 1):
            if transcript_words[i:i+len(normalized_line_words)] == normalized_line_words:
                match_start = word_timestamps[i].start # error here, check properly
                match_end = word_timestamps[i + len(normalized_line_words) - 1].end
                
                # Ensure match falls within parent group's time range
                if match_start >= line_start and match_end <= line_end:
                    for j, original_word in enumerate(line_words):
                        wt = word_timestamps[i + j]
                        word_details.append({
                            'word': original_word,
                            'start': wt.start,
                            'end': wt.end,
                            'id': f'word-{i+j}'  # Temporary ID, reassigned later
                        })
                    return word_details
        
        return []
    
    def process_groups(
        self, 
        groups: List[dict], 
        word_timestamps: List[WordTimestamp]
    ) -> List[ProcessedGroup]:
        """
        Add timestamps to groups, lines, and words.
        """
        processed = []
        
        for idx, group_data in enumerate(groups):
            group_text = group_data.get('group_text', '')
            
            # Get group-level timestamps
            start, end = self.find_phrase_timestamp(group_text, word_timestamps)
            
            if (start, end) == (0.0, 0.0):
                logger.warning(f"Missing timestamp for group {idx}: '{group_text}'")
            
            processed_lines = []
            for line_data in group_data.get('lines', []):
                line_text = line_data.get('text', '')
                font_type = line_data.get('font_type', 'normal')
                
                # Get line timestamps within group bounds
                line_start, line_end = self.find_phrase_timestamp(
                    line_text, word_timestamps, start, end
                )
                
                # Get word-level timestamps
                word_details = self.get_word_timestamps(
                    line_text, word_timestamps, line_start, line_end
                )
                
                processed_lines.append(ProcessedLine(
                    text=line_text,
                    font_type=font_type,
                    start=line_start,
                    end=line_end,
                    words=word_details
                ))
            
            processed.append(ProcessedGroup(
                id=f"group-{idx}",
                group_text=group_text,
                start=start,
                end=end,
                lines=processed_lines
            ))
        
        return processed
    
    def assign_ids(self, groups: List[ProcessedGroup]) -> List[dict]:
        """Assign hierarchical IDs to groups, lines, and words."""
        result = []
        
        for g_idx, group in enumerate(groups):
            group_dict = group.model_dump()
            group_dict['id'] = f"group-{g_idx}"
            
            for l_idx, line in enumerate(group_dict['lines']):
                line['id'] = f"group-{g_idx}-line-{l_idx}"
                
                for w_idx, word in enumerate(line.get('words', [])):
                    word['id'] = f"group-{g_idx}-line-{l_idx}-word-{w_idx}"
            
            result.append(group_dict)
        
        return result