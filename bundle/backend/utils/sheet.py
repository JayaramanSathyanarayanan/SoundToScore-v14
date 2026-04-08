"""
utils/sheet.py — Sheet music generation (best-effort)
Silently skips if MuseScore is not installed.
Returns None gracefully — caller must handle None.
"""
import logging
from pathlib import Path
log = logging.getLogger("soundtoscore")

def generate_sheet(midi_path: str, output_pdf: str,
                   title: str = "SoundToScore") -> bool:
    """
    Try to generate sheet PDF. Returns True if successful, False if not.
    Never raises — always safe to call.
    """
    try:
        from music21 import converter, metadata, environment
        # Check if musescore is available first
        import shutil
        has_mscore = (
            shutil.which('musescore') or
            shutil.which('musescore3') or
            shutil.which('mscore') or
            shutil.which('mscore3')
        )
        if not has_mscore:
            # Silent skip — no musescore installed (expected on Render)
            return False

        score = converter.parse(midi_path)
        md = metadata.Metadata()
        md.title = title
        score.insert(0, md)
        score.write('musicxml.pdf', fp=output_pdf)
        if Path(output_pdf).exists() and Path(output_pdf).stat().st_size > 100:
            log.info(f"Sheet music generated: {output_pdf}")
            return True
        return False
    except Exception as e:
        # Silent — don't log warning spam on every chunk
        return False
