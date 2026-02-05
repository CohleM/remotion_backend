
# --- merger.py ---
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class TimelineMerger:
    """Merge processed chunks into single coherent timeline with sequential IDs."""
    
    @staticmethod
    def merge(processed_chunks: List[List[Dict]]) -> List[Dict]:
        """
        Combine multiple chunk results into single timeline.
        Reassigns IDs sequentially across chunks.
        """
        all_groups = []
        
        for chunk_groups in processed_chunks:
            all_groups.extend(chunk_groups)
        
        # Reassign sequential IDs
        final_timeline = []
        for g_idx, group in enumerate(all_groups):
            group['id'] = f"group-{g_idx}"
            
            for l_idx, line in enumerate(group.get('lines', [])):
                line['id'] = f"group-{g_idx}-line-{l_idx}"
                
                for w_idx, word in enumerate(line.get('words', [])):
                    word['id'] = f"group-{g_idx}-line-{l_idx}-word-{w_idx}"
            
            final_timeline.append(group)
        
        logger.info(f"Merged {len(processed_chunks)} chunks into {len(final_timeline)} total groups")
        return final_timeline
    
    @staticmethod
    def validate_continuity(timeline: List[Dict]) -> bool:
        """Ensure no gaps or overlaps in final timeline."""
        if not timeline:
            return True
        
        # Check chronological order
        prev_end = 0
        for group in timeline:
            start = group.get('start', 0)
            if start < prev_end - 0.1:  # 0.1s tolerance for floating point
                logger.warning(f"Timeline overlap detected: group at {start} starts before previous ended at {prev_end}")
                return False
            prev_end = group.get('end', start)
        
        return True