"""
utils/humanizer.py — MIDI Humanization
Adds slight timing + velocity variation so output sounds natural, not robotic.
"""
import random, logging, math
from pathlib import Path
import pretty_midi
log = logging.getLogger("soundtoscore")

def humanize_midi(midi_path: str, output_path: str,
                  timing_jitter: float = 0.015,
                  velocity_range: int  = 12) -> str:
    """
    Apply subtle human-like variation to MIDI notes.
    timing_jitter: max seconds of timing offset (default 15ms)
    velocity_range: +/- velocity variation
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    random.seed(42)  # reproducible

    for instr in pm.instruments:
        if instr.is_drum:
            continue
        notes = sorted(instr.notes, key=lambda n: n.start)
        for i, note in enumerate(notes):
            # Timing: slight jitter
            jitter = random.uniform(-timing_jitter, timing_jitter)
            note.start = max(0.0, note.start + jitter)
            note.end   = max(note.start + 0.04, note.end + jitter * 0.5)

            # Velocity: musical phrase shape + random variation
            phrase_pos = (i % 16) / 15
            phrase_env = 0.85 + 0.15 * math.sin(math.pi * phrase_pos)
            vel_shift  = random.randint(-velocity_range // 2, velocity_range // 2)
            note.velocity = max(30, min(127, int(note.velocity * phrase_env) + vel_shift))

        instr.notes = notes

    pm.write(output_path)
    log.info(f"Humanized MIDI -> {output_path}")
    return output_path
