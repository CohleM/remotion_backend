
# --- io_handler.py ---
import pickle
import json
import logging
from pathlib import Path
from typing import Any, List
from subtitle_generator.models import WordTimestamp

logger = logging.getLogger(__name__)

# Pickle load (deserialize) from a file

class IOHandler:
    """Handle all file I/O operations."""
    
    @staticmethod
    def load_pickle(pickle_path: str) -> Any:
        """Load word timestamps from pickle file."""
        path = Path(pickle_path)
        if not path.exists():
            raise FileNotFoundError(f"Pickle file not found: {pickle_path}")
            
        with open(path, 'rb') as f:
            data = pickle.load(f)
        logger.info(f"Loaded pickle from {pickle_path}")
        return data
    
    @staticmethod
    def extract_word_timestamps(data: Any) -> List[WordTimestamp]:
        """
        Extract word timestamps from various possible formats.
        Handles both list[WordTimestamp] and objects with .words attribute.
        """
        if isinstance(data, list):
            return [WordTimestamp(**w) if isinstance(w, dict) else w for w in data]
        
        if hasattr(data, 'words'):
            words = data.words
            return [WordTimestamp(**w) if isinstance(w, dict) else w for w in words]
        
        if hasattr(data, 'text'):
            # It's likely a transcription object, return empty list or parse from text
            raise ValueError("Transcription object requires word-level timestamps. Ensure input has word timestamps.")
        
        raise ValueError(f"Unknown data format: {type(data)}")
    
    @staticmethod
    def save_json(data: Any, output_path: str, indent: int = 2):
        """Save data to JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.info(f"Saved output to {output_path}")
