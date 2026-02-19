
# --- models.py ---
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from dataclasses import dataclass
import random


class SubtitleLine(BaseModel):
    text: str = Field(description="Exact word-for-word text from transcript")
    font_type: Literal["normal", "bold", "thin", "italic"] = Field(
        default="normal",
        description="Font weight for visual hierarchy"
    )


class SubtitleGroup(BaseModel):
    group_text: str = Field(description="Consecutive words forming this group")
    lines: List[SubtitleLine] = Field(
        min_items=1, 
        max_items=3,
        description="Lines created from group_text with strategic breaks"
    )
    
    # Populated post-processing
    id: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None


class SubtitleTimeline(BaseModel):
    timeline: List[SubtitleGroup] = Field(
        description="Ordered list of groups covering entire transcript"
    )


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float


class ProcessedLine(SubtitleLine):
    start: float = 0.0
    end: float = 0.0
    words: List[dict] = Field(default_factory=list)
    id: Optional[str] = None


class ProcessedGroup(SubtitleGroup):
    lines: List[ProcessedLine]
    id: str = ""


# NEW: Model for group division step
class GroupDivision(BaseModel):
    """First step: Divide transcript into verbatim groups"""
    groups: List[str] = Field(
        description="List of verbatim text groups from the transcript. Each group must contain exact consecutive words from the transcript."
    )

# Add to subtitle_generator/models.py

class GroupWithHighlight(BaseModel):
    """Group with its associated highlight word for hybrid processing."""
    group_text: str = Field(description="Consecutive verbatim words from transcript")
    highlight_word: Optional[str] = Field(
        default=None,
        description="The emphasis/highlight word for this group (must exist in group_text)"
    )

class GroupDivisionWithHighlights(BaseModel):
    """First step of hybrid: Divide transcript into groups with highlight words."""
    groups: List[GroupWithHighlight] = Field(
        description="List of groups with their highlight words from the transcript."
    )




class FontConfig(BaseModel):
    """
    Font configuration for a subtitle style.
    
    Rules:
    - Highlight font is determined by bold/italic flags (bold takes precedence over italic)
    - Supporting fonts: returns list of available supporting fonts for alternating use
    - Only when bold=True AND italic=True (Combo style), supporting lines randomly choose between normal and italic
    """
    bold: bool = False      # If True, use bold for highlight
    italic: bool = False    # If True and bold=False, use italic for highlight
    normal: bool = True     # Always True for supporting lines (except randomization in Combo)
    
    def get_highlight_font(self) -> Literal["bold", "italic", "normal"]:
        """Determine which font to use for highlight word."""
        if self.bold:
            return "bold"
        elif self.italic:
            return "italic"
        else:
            return "normal"
    
    def get_supporting_fonts(self) -> List[Literal["normal", "italic"]]:
        """
        Get list of available supporting fonts for alternating use.
        
        - Default: ["normal"]
        - Combo style (bold=True, italic=True): ["normal", "italic"] for alternating
        """
        fonts = []
        
        # Always include normal if available
        if self.normal:
            fonts.append("normal")
        
        # In Combo mode, also include italic for variety
        if self.bold and self.italic and self.italic:
            fonts.append("italic")
        
        # Fallback to normal if nothing selected
        if not fonts:
            fonts = ["normal"]
            
        return fonts
    
    def get_supporting_font(self) -> Literal["normal", "italic"]:
        """
        Get single font type for supporting lines (backward compatibility).
        
        - Default: always "normal"
        - Combo style (bold=True, italic=True): randomly choose "normal" or "italic"
        """
        fonts = self.get_supporting_fonts()
        return random.choice(fonts) if len(fonts) > 1 else fonts[0]

    def should_use_highlight(self) -> bool:
        """
        Check if this style uses highlight words.
        Returns True only if bold is enabled (we need a highlight word).
        """
        # Only use highlight separation if bold is True
        # This means NaB, Glow, Combo, GB use highlights
        # NaI, GlowI, GBI, FaB don't use highlight separation
        return self.bold