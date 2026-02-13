# --- post_processor.py (New file) ---
import logging
from typing import List
from subtitle_generator.models import GroupDivision

logger = logging.getLogger(__name__)


class GroupPostProcessor:
    """
    Post-processes LLM-generated groups to enforce word limits.
    Splits oversized groups into smaller chunks while maintaining verbatim text.
    """
    
    def __init__(self, max_words_per_group: int = 8):
        """
        Args:
            max_words_per_group: Maximum words allowed per group. 
                                Groups exceeding this will be split.
        """
        self.max_words = max_words_per_group
    
    def process(self, division: GroupDivision) -> GroupDivision:
        """
        Process a GroupDivision and split any groups exceeding word limit.
        
        Args:
            division: The GroupDivision from LLM
            
        Returns:
            New GroupDivision with all groups within word limit
        """
        new_groups = []
        
        for group_text in division.groups:
            word_count = len(group_text.split())
            
            if word_count <= self.max_words:
                new_groups.append(group_text)
            else:
                # Split oversized group
                split_groups = self._split_group(group_text, word_count)
                new_groups.extend(split_groups)
                logger.info(
                    f"Split oversized group ({word_count} words) into "
                    f"{len(split_groups)} groups: {split_groups}"
                )
        
        return GroupDivision(groups=new_groups)
    
    def _split_group(self, text: str, word_count: int) -> List[str]:
        """
        Split a text group into chunks of roughly equal size.
        
        Args:
            text: The text to split
            word_count: Total word count (pre-calculated)
            
        Returns:
            List of text chunks, each within word limit
        """
        words = text.split()
        
        # Calculate how many groups we need
        # e.g., 12 words with limit 8 -> 2 groups of 6 each
        # e.g., 15 words with limit 8 -> 2 groups (7 and 8) or 3 groups of 5 each
        num_groups = (word_count + self.max_words - 1) // self.max_words  # Ceiling division
        
        # Calculate base size and remainder for even distribution
        base_size = word_count // num_groups
        remainder = word_count % num_groups
        
        result = []
        start_idx = 0
        
        for i in range(num_groups):
            # Distribute remainder across first 'remainder' groups
            chunk_size = base_size + (1 if i < remainder else 0)
            
            chunk_words = words[start_idx:start_idx + chunk_size]
            chunk_text = " ".join(chunk_words)
            result.append(chunk_text)
            
            start_idx += chunk_size
        
        return result
    
    def process_divisions(self, divisions: List[GroupDivision]) -> List[GroupDivision]:
        """
        Process multiple GroupDivisions (e.g., for multiple chunks).
        
        Args:
            divisions: List of GroupDivisions
            
        Returns:
            List of processed GroupDivisions
        """
        return [self.process(d) for d in divisions]