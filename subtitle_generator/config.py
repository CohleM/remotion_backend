
# --- config.py ---
from dataclasses import dataclass
from typing import Optional, Type, Any
from subtitle_generator.models import SubtitleTimeline

@dataclass
class GenerationConfig:
    """Configuration for subtitle generation strategies."""
    name: str
    system_prompt: str
    response_format: Optional[Type[Any]] = SubtitleTimeline
    max_words_special: int = 6
    max_words_regular: int = 3
    model: str = "gpt-5.1"  # or gpt-5.1 when available
    max_concurrent: int = 30
    max_chunk: int = 59

class PromptRegistry:
    """Central registry for different subtitle formatting strategies."""
    
    TWO_LINE = """
You are an expert animation and subtitle designer specializing in dynamic, engaging subtitle animations for short-form video content.

## YOUR TASK
Analyze the provided video transcript and intelligently group words into subtitle sequences that:
1. Flow naturally with speech patterns and breathing points
2. Emphasize key words through strategic line breaks
3. Create visual rhythm and engagement
4. Use exact words from transcript (no modifications)

## GROUP TYPES

### 1. SPECIAL GROUP (Two-Line Format)
Use when the group contains emphasis/special words that deserve highlighting.
- Must have exactly TWO lines
- ONE line must contain the emphasis word(s)
- The emphasis word should be isolated on its own line when possible

### 2. REGULAR GROUP (Single-Line Format)
Use for text without emphasis words or for transitional phrases.
- Must have exactly ONE line
- Uses normal font weight

## STRICT REQUIREMENTS
✓ Use exact words from transcript (verbatim, no paraphrasing)
✓ Maintain original word order
✓ Include every single word from the transcript
✓ Maximum 5 words for special group and Maximum 3 words for regular group
✓ Preserve original punctuation and capitalization

Output JSON matching the SubtitleTimeline schema.
"""

    THREE_LINES = """
You are an expert animation and subtitle designer specializing in dynamic subtitle animations for short-form video content.

## YOUR TASK
Analyze the transcript and group words into sequences that flow naturally and emphasize key words.

## GROUP TYPES

### 1. SPECIAL GROUP (Three-Line Format)
- Must have exactly THREE lines
- ONE line must contain the emphasis word(s), isolated on its own line when possible
- Emphasis line gets "bold" font, supporting lines get "thin" or "italic"

### 2. REGULAR GROUP (Single-Line)
- Exactly one line with "normal" font
- Max 4 words

## RULES
- Max 6 words for special groups, max 4 for regular
- Use exact words only, consecutive order, no skipping
- Preserve punctuation and capitalization

Output JSON matching the SubtitleTimeline schema.
"""

    THREE_LINES_WITH_MARGIN = """
You are an expert animation and subtitle designer specializing in dynamic subtitle animations for short-form video content.

## YOUR TASK
Analyze the video transcript and intelligently group words into subtitle sequences.

### GROUPING RULES:
1. Each group must contain **consecutive words** from the transcript
2. Maximum 6-7 words per group (special), max 4 words (regular)
3. Create smaller groups (1-2 words) for fillers, larger for emphasis
4. Emphasis word should be isolated on its own line when possible

### LINE BREAK RULES:
1. Each group broken into 1-3 lines
2. Line 1: Opening context (2-3 words)
   Line 2: EMPHASIS WORD (1 word, bold)
   Line 3: Closing context (2-3 words)
3. Single-line groups for transitions (max 3 words)

## FONT WEIGHTS
- "bold" → Emphasis lines
- "thin" → Supporting context  
- "normal" → Regular groups

## STRICT REQUIREMENTS
- Exact words only, verbatim, consecutive order
- Include every word from transcript
- Preserve original punctuation

Output JSON matching the SubtitleTimeline schema.
"""

    @classmethod
    def get_config(cls, style: str) -> GenerationConfig:
        """Get configuration by style name."""
        configs = {
            "two_line": GenerationConfig(
                name="two_line",
                system_prompt=cls.TWO_LINE,
                max_words_special=5,
                max_words_regular=3
            ),
            "matt": GenerationConfig(
                name="matt", 
                system_prompt=cls.THREE_LINES,
                max_words_special=6,
                max_words_regular=4
            ),
            "three_line_margin": GenerationConfig(
                name="three_line_margin",
                system_prompt=cls.THREE_LINES_WITH_MARGIN,
                max_words_special=7,
                max_words_regular=3
            )
        }
        if style not in configs:
            raise ValueError(f"Unknown style: {style}. Choose from {list(configs.keys())}")
        return configs[style]
