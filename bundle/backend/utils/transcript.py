"""Generate human-readable note transcript from MIDI."""
from pathlib import Path
import pretty_midi
NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def _note_name(n: int) -> str:
    return f"{NOTE_NAMES[n%12]}{(n//12)-1}"

def generate_transcript(midi_path: str, output_txt: str, tempo: int = 120) -> str:
    if not Path(midi_path).exists():
        return ""
    try:
        pm = pretty_midi.PrettyMIDI(midi_path)
        lines = []
        for instr in pm.instruments:
            for note in sorted(instr.notes, key=lambda n: n.start):
                lines.append(f"{_note_name(note.pitch)} vel:{note.velocity} "
                             f"t={note.start:.3f}s dur={note.end-note.start:.3f}s")
        text = "\n".join(lines)
        Path(output_txt).write_text(text or "No notes detected", encoding="utf-8")
        return text
    except Exception as e:
        Path(output_txt).write_text(f"Transcript error: {e}", encoding="utf-8")
        return ""
