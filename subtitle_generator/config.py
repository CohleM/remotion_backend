
# --- config.py ---
from dataclasses import dataclass
from typing import Optional, Type, Any
from subtitle_generator.models import SubtitleTimeline,GroupDivision, GroupDivisionWithHighlights, FontConfig
from subtitle_generator.prompts import (
    GRADIENT_BASE_ITALIC, NORMAL_AND_BOLD, THREE_LINES, TWO_LINES, GRADIENT_BASE, HYBRID_GROUP_DIVISION_NO_HIGHLIGHT,
    THREE_LINES_GROUP_DIVISION, TWO_LINES_GROUP_DIVISION,  COMBO,NORMAL_AND_ITALIC
)

from subtitle_generator.prompts import HYBRID_GROUP_DIVISION
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

# Add to subtitle_generator/config.py prompts import and GenerationConfig

# Add to the imports at top:
from subtitle_generator.prompts import (
    # ... existing imports ...
    HYBRID_GROUP_DIVISION,  # NEW
)
from dataclasses import dataclass, field

# Update GenerationConfig to include hybrid format:
@dataclass
class GenerationConfig:
    """Configuration for subtitle generation strategies."""
    name: str
    system_prompt:  Optional[str] = None
    group_division_prompt: Optional[str] = None
    response_format: Optional[Type[Any]] = SubtitleTimeline
    group_division_format: Optional[Type[Any]] = GroupDivision  # For two-step
    # NEW: For hybrid approach
    hybrid_division_format: Optional[Type[Any]] = GroupDivisionWithHighlights  # NEW
    max_words_special: int = 6
    max_words_regular: int = 3
    model: str = "gpt-5.1"
    max_concurrent: int = 30
    max_chunk: int = 59
    max_words_per_group: int = 8
    use_hybrid: bool = True
    # NEW: Line division strategy
    max_words_per_line: int = 3  # NEW: For rule-based line division
    font_config: FontConfig = field(default_factory=FontConfig)
    

class PromptRegistry:
    """Central registry for different subtitle formatting strategies."""

    @classmethod
    def get_config(cls, style: str) -> GenerationConfig:
        """Get configuration by style name."""
        configs = {
             "FaB": GenerationConfig(
                name="Fade and Blur",
                # system_prompt=FADE_AND_BLUR,
                group_division_prompt=HYBRID_GROUP_DIVISION_NO_HIGHLIGHT,  # NEW,
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=9,
                font_config=FontConfig(bold=False, normal=True, italic=False) # when bold is false, it will use divide_no_highlight line divider
            ),
             "Combo": GenerationConfig(
                name="Combo",
                group_division_prompt=HYBRID_GROUP_DIVISION, 
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=True, normal=True, italic=True)
            ),
             "NaI": GenerationConfig(
                name="Normal and Italic",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=False, normal=True, italic=True)
            ),
             "NaB": GenerationConfig(
                name="Normal and Bold",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=True, normal=True, italic=False)
            ),
             "EW": GenerationConfig(
                name="Equal Width",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=True, normal=True, italic=True)
            ),
             "GB": GenerationConfig(
                name="Gradient Base",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=True, normal=True, italic=False)
            ),
             "Glow": GenerationConfig(
                name="Glow",
                # system_prompt=NORMAL_AND_BOLD,
                # group_division_prompt=THREE_LINES_GROUP_DIVISION,  # NEW,
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_special=7,
                max_words_regular=3,
                max_words_per_group=8,
                font_config=FontConfig(bold=True, normal=True, italic=False)
            ),
             "GlowI": GenerationConfig(
                name="Glow Italic",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=False, normal=True, italic=True)
            ),
             "GBI": GenerationConfig(
                name="Gradient Base Italic",
                group_division_prompt=HYBRID_GROUP_DIVISION,  # NEW
                hybrid_division_format=GroupDivisionWithHighlights,
                max_words_per_group=8,
                font_config=FontConfig(bold=False, normal=True, italic=True)
            ),


        }
        if style not in configs:
            raise ValueError(f"Unknown style: {style}. Choose from {list(configs.keys())}")
        return configs[style]


