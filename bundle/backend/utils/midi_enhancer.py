"""Enhance MIDI: quantize timing, smooth velocity, merge nearby same-pitch notes."""
import logging, math
from pathlib import Path
import pretty_midi
log = logging.getLogger("soundtoscore")

def enhance_midi(midi_path: str, output_path: str, grid: float = 0.0625) -> str:
    pm = pretty_midi.PrettyMIDI(midi_path)
    for instr in pm.instruments:
        if instr.is_drum:
            continue
        # Quantize to grid
        for n in instr.notes:
            n.start = round(n.start / grid) * grid
            n.end   = max(n.start + 0.05, round(n.end / grid) * grid)
        # Smooth velocity — apply a gentle curve (quieter at edges)
        notes = sorted(instr.notes, key=lambda n: n.start)
        total = len(notes)
        for i, n in enumerate(notes):
            pos_ratio = i / max(total - 1, 1)
            envelope  = 0.7 + 0.3 * math.sin(math.pi * pos_ratio)
            n.velocity = max(40, min(127, int(n.velocity * envelope)))
        # Merge nearby same-pitch notes (gap < 0.05s)
        merged = []
        for n in notes:
            if merged and merged[-1].pitch == n.pitch and (n.start - merged[-1].end) < 0.05:
                merged[-1].end = n.end
                merged[-1].velocity = max(merged[-1].velocity, n.velocity)
            else:
                merged.append(n)
        instr.notes = merged
    pm.write(output_path)
    log.info(f"MIDI enhanced -> {output_path}")
    return output_path
