import subprocess, logging
from pathlib import Path
log = logging.getLogger("soundtoscore")

def preprocess_audio(input_path: str, output_path: str, sr: int = 16000) -> None:
    if not Path(input_path).exists():
        raise FileNotFoundError(f"Input not found: {input_path}")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", str(sr), "-ac", "1",
           "-sample_fmt", "s16", "-af", "loudnorm", "-vn", output_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {r.stderr[-600:]}")
    if not Path(output_path).exists():
        raise FileNotFoundError("FFmpeg produced no output")
    log.info(f"Preprocessed -> {output_path}")
