"""
utils/effects.py — Audio post-processing with FFmpeg
Applies reverb, EQ, and normalization to synthesized audio.
Free-tier safe: uses FFmpeg only, no heavy libraries.
"""
import subprocess, logging, shutil
from pathlib import Path
log = logging.getLogger("soundtoscore")

def apply_effects(input_wav: str, output_wav: str,
                  reverb: bool = True, eq: bool = True) -> str:
    """Apply reverb + EQ to WAV using FFmpeg audio filters."""
    if not Path(input_wav).exists():
        raise FileNotFoundError(f"Input not found: {input_wav}")

    filters = []

    if eq:
        # Gentle EQ: cut harsh highs, boost warmth
        filters.append("equalizer=f=8000:width_type=o:width=2:g=-3")
        filters.append("equalizer=f=300:width_type=o:width=2:g=+2")
        filters.append("equalizer=f=60:width_type=o:width=2:g=+1")

    if reverb:
        # Convolution reverb via aecho (hall-like)
        filters.append("aecho=0.8:0.9:40|70:0.4|0.25")

    # Always normalize
    filters.append("loudnorm")

    af = ",".join(filters) if filters else "loudnorm"

    cmd = ["ffmpeg", "-y", "-i", input_wav, "-af", af, output_wav]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        log.warning(f"Effects failed: {r.stderr[-300:]} — using dry audio")
        shutil.copy(input_wav, output_wav)
    else:
        log.info(f"Effects applied -> {output_wav}")
    return output_wav
