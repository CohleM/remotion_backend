# Update subtitle_generator/utils/hybrid_line_divider.py
import re
import logging
import random
from typing import List, Dict, Optional, Tuple, Any
from subtitle_generator.models import (
    GroupWithHighlight, 
    SubtitleGroup, 
    SubtitleLine,
    FontConfig,
    GroupDivisionWithHighlights
)

logger = logging.getLogger(__name__)


class HybridLineDivider:
    """
    Rule-based line divider for hybrid subtitle processing.
    Divides groups into lines using highlight word as anchor.
    Supports configurable fonts per style.
    """
    
    def __init__(self, max_words_per_line: int = 3, font_config: Optional[FontConfig] = None):
        self.max_words = max_words_per_line
        self.font_config = font_config or FontConfig()  # Default to normal only
        random.seed()  # Initialize random for font selection
    
    def divide_group(self, group: GroupWithHighlight) -> SubtitleGroup:
        """
        Divide a single group into lines based on highlight word and font config.
        """
        text = group.group_text
        highlight = group.highlight_word

        # Check if this style actually uses highlight words
        # If not, treat as normal group without highlight separation
        if not self.font_config.should_use_highlight():
            return self._divide_without_highlight(text)
        
        # If no highlight or highlight not in text, treat as normal group
        if not highlight or highlight not in text:
            return self._divide_without_highlight(text)
        
        # Split text into words preserving order
        words = text.split()
        
        # Find highlight position
        try:
            clean_words = [self._clean_word(w) for w in words]
            clean_highlight = self._clean_word(highlight)
            highlight_idx = clean_words.index(clean_highlight)
        except ValueError:
            logger.warning(f"Highlight word '{highlight}' not found in '{text}'")
            return self._divide_without_highlight(text)
        
        # Split into before and after highlight
        before_words = words[:highlight_idx]
        after_words = words[highlight_idx + 1:]
        
        # Build lines
        lines = []
        
        # Get fonts from config
        highlight_font = self.font_config.get_highlight_font()
        supporting_fonts = self.font_config.get_supporting_fonts()  # Get list of available supporting fonts
        
        # Handle before highlight - split into chunks of max_words
        # Alternate between available supporting fonts
        if before_words:
            before_chunks = self._chunk_words(before_words, self.max_words)
            for i, chunk in enumerate(before_chunks):
                # Cycle through supporting fonts: 0, 1, 0, 1, etc.
                font_idx = i % len(supporting_fonts)
                lines.append(SubtitleLine(
                    text=" ".join(chunk),
                    font_type=supporting_fonts[font_idx]
                ))
        
        # Add highlight line with configured highlight font (bold or italic)
        lines.append(SubtitleLine(
            text=highlight,
            font_type=highlight_font
        ))
        
        # Handle after highlight - split into chunks of max_words
        # Continue alternating pattern from where we left off
        if after_words:
            after_chunks = self._chunk_words(after_words, self.max_words)
            start_idx = len(before_chunks) % len(supporting_fonts) if before_words else 0
            for i, chunk in enumerate(after_chunks):
                font_idx = (start_idx + i) % len(supporting_fonts)
                lines.append(SubtitleLine(
                    text=" ".join(chunk),
                    font_type=supporting_fonts[font_idx]
                ))
        
        # Ensure we don't exceed 3 lines total
        lines = self._optimize_lines(lines, supporting_fonts)
        
        return SubtitleGroup(
            group_text=text,
            lines=lines
        )
    
    def _clean_word(self, word: str) -> str:
        """Remove punctuation for matching."""
        return re.sub(r'[^\w\s]', '', word.lower()).strip()
    
    def _chunk_words(self, words: List[str], max_size: int) -> List[List[str]]:
        """Split word list into chunks of max_size."""
        if not words:
            return []
        
        chunks = []
        current_chunk = []
        
        for word in words:
            if len(current_chunk) >= max_size:
                chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append(word)
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _divide_without_highlight(self, text: str) -> SubtitleGroup:
        """Divide group without highlight word (all supporting fonts)."""
        words = text.split()
        
        # Simple chunking
        chunks = self._chunk_words(words, self.max_words)
        
        supporting_fonts = self.font_config.get_supporting_fonts()
        
        # Alternate between supporting fonts
        lines = []
        for i, chunk in enumerate(chunks):
            font_idx = i % len(supporting_fonts)
            lines.append(SubtitleLine(
                text=" ".join(chunk), 
                font_type=supporting_fonts[font_idx]
            ))
        
        return SubtitleGroup(group_text=text, lines=lines)
    
    def _optimize_lines(self, lines: List[SubtitleLine], supporting_fonts: List[str]) -> List[SubtitleLine]:
        """
        Ensure we have at most 3 lines.
        If more than 3, merge supporting lines intelligently while alternating fonts.
        """
        if len(lines) <= 3:
            return lines
        
        # Find highlight line index
        highlight_font = self.font_config.get_highlight_font()
        highlight_idx = None
        
        for i, line in enumerate(lines):
            if line.font_type == highlight_font:
                highlight_idx = i
                break
        
        if highlight_idx is None:
            # No highlight found, just take first 3 chunks with alternating fonts
            result = []
            for i in range(min(3, len(lines))):
                font_idx = i % len(supporting_fonts)
                result.append(SubtitleLine(text=lines[i].text, font_type=supporting_fonts[font_idx]))
            return result
        
        # Strategy: Keep highlight line, merge others
        before = lines[:highlight_idx]
        highlight = lines[highlight_idx]
        after = lines[highlight_idx + 1:]
        
        # Merge strategy: reduce to max 1 line before and 1 line after
        while len(before) > 1 and len(after) > 1:
            if len(before) >= len(after):
                # Merge last two before lines - use the font of the first one to maintain alternation pattern
                merged_text = before[-2].text + " " + before[-1].text
                before[-2] = SubtitleLine(text=merged_text, font_type=before[-2].font_type)
                before.pop(-1)
            else:
                # Merge first two after lines
                merged_text = after[0].text + " " + after[1].text
                after[0] = SubtitleLine(text=merged_text, font_type=after[0].font_type)
                after.pop(1)
        
        # If still over 3 lines, merge all extras into adjacent lines
        while len(before) + 1 + len(after) > 3:
            if len(before) > 1:
                # Merge last two before
                merged_text = before[-2].text + " " + before[-1].text
                before[-2] = SubtitleLine(text=merged_text, font_type=before[-2].font_type)
                before.pop(-1)
            elif len(after) > 1:
                # Merge first two after
                merged_text = after[0].text + " " + after[1].text
                after[0] = SubtitleLine(text=merged_text, font_type=after[0].font_type)
                after.pop(1)
            else:
                break
        
        # Ensure alternating fonts for final result if we have 2 supporting lines
        result = before + [highlight] + after
        if len(result) == 3 and len(supporting_fonts) >= 2:
            # Check if both supporting lines have same font
            supporting_indices = [i for i, line in enumerate(result) if line.font_type != highlight_font]
            if len(supporting_indices) == 2:
                idx1, idx2 = supporting_indices
                if result[idx1].font_type == result[idx2].font_type:
                    # They have same font, change second one to alternate
                    current_font = result[idx1].font_type
                    alternate_font = supporting_fonts[1] if current_font == supporting_fonts[0] else supporting_fonts[0]
                    result[idx2] = SubtitleLine(text=result[idx2].text, font_type=alternate_font)
        
        return result
    
    def divide_groups(self, groups: List[GroupWithHighlight]) -> List[SubtitleGroup]:
        """Process multiple groups."""
        return [self.divide_group(g) for g in groups]


class HybridPostProcessor:
    """
    Post-process groups with highlights, splitting oversized groups
    and correctly assigning highlight words to split parts.
    """
    
    def __init__(self, max_words_per_group: int = 8):
        self.max_words = max_words_per_group
    
    def process(
        self, 
        division: 'GroupDivisionWithHighlights'
    ) -> List[GroupWithHighlight]:
        """
        Split oversized groups and assign highlight words correctly.
        """
        from subtitle_generator.models import GroupDivisionWithHighlights
        
        result = []
        
        for group in division.groups:
            word_count = len(group.group_text.split())
            
            if word_count <= self.max_words:
                result.append(group)
            else:
                # Split and distribute highlight
                split_groups = self._split_group_with_highlight(group)
                result.extend(split_groups)
        
        return result
    
    def _split_group_with_highlight(
        self, 
        group: GroupWithHighlight
    ) -> List[GroupWithHighlight]:
        """
        Split oversized group and determine which part gets the highlight.
        """
        words = group.group_text.split()
        highlight = group.highlight_word
        
        # Find highlight position
        try:
            clean_words = [re.sub(r'[^\w]', '', w.lower()) for w in words]
            clean_highlight = re.sub(r'[^\w]', '', highlight.lower()) if highlight else ""
            highlight_idx = clean_words.index(clean_highlight) if clean_highlight else -1
        except ValueError:
            highlight_idx = -1
        
        # Calculate split point
        total_words = len(words)
        mid_point = total_words // 2
        
        # Adjust split to not break in middle of a potential highlight
        split_point = mid_point
        
        # Split words
        first_half = words[:split_point]
        second_half = words[split_point:]
        
        first_text = " ".join(first_half)
        second_text = " ".join(second_half)
        
        # Determine which half gets the highlight
        first_highlight = None
        second_highlight = None
        
        if highlight_idx >= 0 and highlight_idx < split_point:
            # Highlight is in first half
            first_highlight = highlight
            # Try to find a secondary highlight in second half (longest word)
            if len(second_half) > 1:
                second_highlight = max(second_half, key=len)
        elif highlight_idx >= split_point:
            # Highlight is in second half
            second_highlight = highlight
            # Try to find secondary in first half
            if len(first_half) > 1:
                first_highlight = max(first_half, key=len)
        else:
            # No highlight found, assign longest words
            if len(first_half) > 1:
                first_highlight = max(first_half, key=len)
            if len(second_half) > 1:
                second_highlight = max(second_half, key=len)
        
        result = []
        
        if first_half:
            result.append(GroupWithHighlight(
                group_text=first_text,
                highlight_word=first_highlight
            ))
        
        if second_half:
            result.append(GroupWithHighlight(
                group_text=second_text,
                highlight_word=second_highlight
            ))
        
        return result
    
    def process_divisions(
        self, 
        divisions: List['GroupDivisionWithHighlights']
    ) -> List[List[GroupWithHighlight]]:
        """Process multiple divisions (one per chunk)."""
        return [self.process(d) for d in divisions]