"""Apply semitone transposition to MIDI for instrument key correction."""
import logging
from pathlib import Path
import pretty_midi
log = logging.getLogger("soundtoscore")

def transpose_midi(midi_path: str, output_path: str, semitones: int) -> str:
    if semitones == 0:
        import shutil; shutil.copy(midi_path, output_path)
        return output_path
    pm = pretty_midi.PrettyMIDI(midi_path)
    for instr in pm.instruments:
        if not instr.is_drum:
            for note in instr.notes:
                note.pitch = max(0, min(127, note.pitch + semitones))
    pm.write(output_path)
    log.info(f"Transposed {semitones:+d} semitones -> {output_path}")
    return output_path
