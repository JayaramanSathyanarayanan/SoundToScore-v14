"""Clean MIDI: remove short notes, low velocity, duplicates, fix overlaps."""
import logging
from pathlib import Path
import pretty_midi
log = logging.getLogger("soundtoscore")

def clean_midi(midi_path: str, output_path: str,
               min_duration: float = 0.08, min_velocity: int = 45) -> str:
    pm = pretty_midi.PrettyMIDI(midi_path)
    total_before = sum(len(i.notes) for i in pm.instruments)
    for instr in pm.instruments:
        # Remove short / quiet notes
        instr.notes = [n for n in instr.notes
                       if (n.end - n.start) >= min_duration and n.velocity >= min_velocity]
        # Sort by start time
        instr.notes.sort(key=lambda n: n.start)
        # Remove exact duplicates
        seen, unique = set(), []
        for n in instr.notes:
            key = (n.pitch, round(n.start, 3))
            if key not in seen:
                seen.add(key); unique.append(n)
        instr.notes = unique
        # Fix overlaps for same pitch
        for i in range(len(instr.notes) - 1):
            a, b = instr.notes[i], instr.notes[i+1]
            if a.pitch == b.pitch and a.end > b.start:
                a.end = b.start - 0.01
    pm.write(output_path)
    total_after = sum(len(i.notes) for i in pm.instruments)
    log.info(f"MIDI clean: {total_before} -> {total_after} notes")
    return output_path
