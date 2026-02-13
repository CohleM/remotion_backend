
# --- config.py ---
from dataclasses import dataclass
from typing import Optional, Type, Any
from subtitle_generator.models import SubtitleTimeline,GroupDivision
from subtitle_generator.prompts import (
    THREE_LINES, TWO_LINES, 
    THREE_LINES_GROUP_DIVISION, TWO_LINES_GROUP_DIVISION
)
# @dataclass
# class GenerationConfig:
#     """Configuration for subtitle generation strategies."""
#     name: str
#     system_prompt: str
#     response_format: Optional[Type[Any]] = SubtitleTimeline
#     max_words_special: int = 6
#     max_words_regular: int = 3
#     model: str = "gpt-5.1"  # or gpt-5.1 when available
#     max_concurrent: int = 30
#     max_chunk: int = 59

@dataclass
class GenerationConfig:
    """Configuration for subtitle generation strategies."""
    name: str
    system_prompt: str
    group_division_prompt: Optional[str] = None  # NEW: Prompt for step 1
    response_format: Optional[Type[Any]] = SubtitleTimeline
    group_division_format: Optional[Type[Any]] = GroupDivision  # NEW: Format for step 1
    max_words_special: int = 6
    max_words_regular: int = 3
    model: str = "gpt-5.1"
    max_concurrent: int = 30
    max_chunk: int = 59

class PromptRegistry:
    """Central registry for different subtitle formatting strategies."""

    @classmethod
    def get_config(cls, style: str) -> GenerationConfig:
        """Get configuration by style name."""
        configs = {
            "basic": GenerationConfig(
                name="two_line",
                system_prompt=TWO_LINES,
                max_words_special=5,
                max_words_regular=3
            ),
            "matt": GenerationConfig(
                name="matt", 
                system_prompt=THREE_LINES,
                group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW
                max_words_special=6,
                max_words_regular=4
            ),
            "ThreeLines": GenerationConfig(
                name="three_line_margin",
                system_prompt=THREE_LINES,
                group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW
                max_words_special=7,
                max_words_regular=3
            ),
            "jack": GenerationConfig(
                name="jack",
                system_prompt=THREE_LINES,
                group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW
                max_words_special=7,
                max_words_regular=3
            ),
            "nick": GenerationConfig(
                name="nick",
                system_prompt=THREE_LINES,
                group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW
                max_words_special=7,
                max_words_regular=3
            ),
            "laura": GenerationConfig(
                name="laura",
                system_prompt=THREE_LINES,
                group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW
                max_words_special=7,
                max_words_regular=3
            )
        }
        if style not in configs:
            raise ValueError(f"Unknown style: {style}. Choose from {list(configs.keys())}")
        return configs[style]
