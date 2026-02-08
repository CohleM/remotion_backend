from pydub import AudioSegment
import time
import ffmpeg
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_mp4_to_mp3(input_path, output_path=None, bitrate="192k", max_retries=3, retry_delay=2):
    """
    Convert MP4 to MP3 using pydub with retry logic
    Outputs 16kHz mono MP3
    
    Args:
        input_path: Path to input MP4 file
        output_path: Path to output MP3 file
        bitrate: Audio bitrate (default: "192k")
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay in seconds between retries (default: 2)
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_audio.mp3"


    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_retries}: Converting {input_path} to {output_path}")
            
            # Load audio
            audio = AudioSegment.from_file(input_path, format="mp4")
            
            # Convert to mono
            audio = audio.set_channels(1)
            
            # Set sample rate to 16kHz
            audio = audio.set_frame_rate(16000)
            
            # Export with specified settings
            audio.export(
                output_path, 
                format="mp3",
                bitrate=bitrate,
                parameters=["-q:a", "2"]  # VBR quality
            )
            
            logger.info(f"Conversion successful: {output_path} (16kHz mono)")
            return output_path
            
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return output_path  # Don't retry if file doesn't exist
            
        except Exception as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"All {max_retries} attempts failed for {input_path}")
                return output_path
    
    return output_path

# Usage
if __name__ == "__main__":
    success = convert_mp4_to_mp3(
        "input1.mp4", 
        "output.mp3",
        bitrate="96k",  # Lower bitrate is fine for 16kHz mono
        max_retries=3,
        retry_delay=2
    )
    
    if success:
        print("✓ Conversion completed successfully (16kHz mono)")
    else:
        print("✗ Conversion failed after all retries")


def convert_video_lowres(input_file, output_file=None, target_height=360):
    """
    Converts a video to a specified vertical resolution (height) while keeping aspect ratio and audio.
    
    Parameters:
        input_file (str): Path to the input video file.
        output_file (str, optional): Path to save the converted video. 
                                     If None, adds '_{target_height}p' to the input filename.
        target_height (int): Desired height in pixels (e.g., 360 for 360p, 480 for 480p).
    """
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_{target_height}p{ext}"
    
    try:
        # Build the scale filter dynamically based on target height
        scale_filter = f"scale=-2:{target_height}"
        
        # Run ffmpeg conversion
        (
            ffmpeg
            .input(input_file)
            .output(output_file, vf=scale_filter, vcodec='libx264', acodec='aac', strict='experimental')
            .run(overwrite_output=True)
        )
        print(f"Video successfully converted to {target_height}p: {output_file}")
        return output_file
    except ffmpeg.Error as e:
        print("Error during conversion:", e)
        raise


def get_video_info(video_path):
    probe = ffmpeg.probe(video_path)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')

    width = int(video_info['width'])
    height = int(video_info['height'])
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    duration = float(video_info['duration'])
    fps = 30

    return width, height, duration, fps