"""
services/optimization.py
Smart optimization: decide pipeline steps based on file size/duration.
Free-tier aware.
"""
import logging
from pathlib import Path
log = logging.getLogger("soundtoscore")

def decide_pipeline(file_size_bytes: int, duration_sec: float) -> dict:
    """
    Return pipeline flags based on input complexity.
    Larger/longer files skip heavy steps to stay within free-tier limits.
    """
    mb = file_size_bytes / 1024 / 1024

    use_demucs      = mb < 8 and duration_sec < 45
    use_sheet       = True
    use_orchestra   = mb < 10 and duration_sec < 60
    use_humanize    = True
    use_effects     = True
    max_chunks      = 999 if mb < 20 else 6   # cap chunks for large files

    plan = {
        "use_demucs":    use_demucs,
        "use_sheet":     use_sheet,
        "use_orchestra": use_orchestra,
        "use_humanize":  use_humanize,
        "use_effects":   use_effects,
        "max_chunks":    max_chunks,
    }
    log.info(f"Pipeline plan: {mb:.1f}MB / {duration_sec:.0f}s -> {plan}")
    return plan
