
# --- models.py ---
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from dataclasses import dataclass


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
