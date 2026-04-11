"""
utils/midi_cleaner.py — SoundToScore V14
==========================================
Professional MIDI Sanitization Engine.

Global steps (always applied):
  1. Noise removal — duration < minDuration or velocity < 20
  2. Pitch range filtering — per instrumentProfile
  3. Merge repeated notes — same pitch, gap < 0.05s
  4. Remove unrealistic pitch jumps — > maxJump semitones
  5. Timing quantization — snap to 0.05s grid
  6. Velocity smoothing — local 3-note average
  7. Legato — gap < 0.05s → extend previous note end
  8. Monophonic enforcement (brass/woodwind) — last-note-wins
"""
import logging, math
from pathlib import Path
import pretty_midi

log = logging.getLogger("soundtoscore")

# ── Per-instrument profiles ────────────────────────────────────────────────
# (minPitch, maxPitch, monophonic, maxJump, minDuration, velocityFloor)
INSTR_PROFILES = {
    # Brass band
    "soprano_cornet":  (58, 94,  True,  14, 0.06, 50),
    "solo_cornet":     (55, 91,  True,  14, 0.06, 50),
    "repiano_cornet":  (55, 88,  True,  14, 0.06, 50),
    "cornet_2nd":      (52, 84,  True,  14, 0.06, 50),
    "cornet_3rd":      (48, 81,  True,  14, 0.06, 50),
    "flugelhorn":      (52, 84,  True,  12, 0.06, 50),
    "solo_tenor_horn": (48, 79,  True,  12, 0.06, 50),
    "tenor_horn_1st":  (48, 76,  True,  12, 0.06, 50),
    "tenor_horn_2nd":  (45, 74,  True,  12, 0.06, 50),
    "baritone_1st":    (45, 76,  True,  12, 0.07, 50),
    "baritone_2nd":    (43, 74,  True,  12, 0.07, 50),
    "euphonium":       (40, 72,  True,  12, 0.07, 50),
    "trombone_1st":    (40, 72,  True,  10, 0.07, 50),
    "trombone_2nd":    (36, 69,  True,  10, 0.07, 50),
    "bass_trombone":   (28, 65,  True,  10, 0.08, 50),
    "eb_bass":         (28, 60,  True,   8, 0.08, 50),
    "bbb_bass":        (24, 55,  True,   8, 0.08, 50),
    # Trumpet family
    "trumpet_bb":      (55, 94,  True,  14, 0.06, 50),
    "trumpet_c":       (58, 96,  True,  14, 0.06, 50),
    "trumpet_d":       (60, 98,  True,  14, 0.06, 50),
    "trumpet_eb":      (62, 100, True,  14, 0.06, 50),
    "piccolo_trumpet": (65, 102, True,  14, 0.05, 50),
    "pocket_trumpet":  (55, 94,  True,  14, 0.06, 50),
    "muted_trumpet":   (55, 90,  True,  12, 0.06, 50),
    "harmon_trumpet":  (55, 90,  True,  12, 0.06, 50),
    "french_horn":     (35, 77,  True,  10, 0.08, 50),
    "tenor_horn":      (48, 76,  True,  12, 0.06, 50),
    "baritone":        (45, 76,  True,  12, 0.07, 50),
    "tuba":            (28, 60,  True,   8, 0.08, 50),
    # Piano
    "concert_grand":   (21, 108, False, 24, 0.04, 20),
    "baby_grand":      (21, 108, False, 24, 0.04, 20),
    "upright":         (21, 108, False, 24, 0.04, 20),
    "studio_piano":    (21, 108, False, 24, 0.04, 20),
    "honky_tonk":      (21, 108, False, 24, 0.04, 20),
    "felt_piano":      (21, 108, False, 24, 0.04, 20),
    "prepared_piano":  (21, 108, False, 24, 0.04, 20),
    "rhodes":          (28, 103, False, 24, 0.04, 20),
    "wurlitzer":       (28, 100, False, 24, 0.04, 20),
    "fm_piano":        (28, 103, False, 24, 0.04, 20),
    # Strings
    "violin":          (55, 103, False, 20, 0.05, 35),
    "viola":           (48, 88,  False, 20, 0.05, 35),
    "cello":           (36, 76,  False, 18, 0.06, 35),
    "double_bass":     (28, 67,  False, 14, 0.07, 35),
    "string_ensemble": (28, 103, False, 22, 0.05, 35),
    "pizzicato":       (36, 103, False, 22, 0.04, 35),
    "tremolo":         (36, 103, False, 22, 0.05, 35),
    "staccato":        (36, 103, False, 22, 0.04, 35),
    # Guitar/Bass
    "acoustic_guitar": (40, 88,  False, 24, 0.05, 30),
    "electric_guitar": (40, 96,  False, 24, 0.05, 30),
    "distortion_guitar":(40,100, False, 24, 0.05, 30),
    "electric_bass":   (28, 60,  True,  12, 0.06, 30),
    "slap_bass":       (28, 55,  True,  12, 0.05, 30),
    # Woodwinds
    "flute":           (60, 96,  True,  14, 0.06, 40),
    "piccolo":         (74, 108, True,  14, 0.05, 40),
    "alto_flute":      (55, 88,  True,  14, 0.06, 40),
    "clarinet":        (50, 92,  True,  14, 0.06, 40),
    "bass_clarinet":   (38, 80,  True,  12, 0.06, 40),
    "oboe":            (58, 91,  True,  12, 0.06, 40),
    "bassoon":         (34, 72,  True,  10, 0.07, 40),
    "alto_sax":        (49, 80,  True,  14, 0.06, 40),
    "tenor_sax":       (44, 76,  True,  14, 0.06, 40),
    "baritone_sax":    (36, 69,  True,  12, 0.07, 40),
    # Percussion (pitched)
    "timpani":         (36, 60,  False, 12, 0.05, 25),
    "glockenspiel":    (72, 108, False, 24, 0.04, 25),
    "xylophone":       (65, 96,  False, 24, 0.04, 25),
    "tubular_bells":   (60, 84,  False, 18, 0.05, 25),
    # Unpitched percussion — skip pitch range, velocity gate only
    "drum_kit":        (None, None, False, 127, 0.02, 25),
    "snare_drum":      (None, None, False, 127, 0.02, 25),
    "bass_drum":       (None, None, False, 127, 0.02, 25),
    "cymbals":         (None, None, False, 127, 0.02, 25),
    "triangle":        (None, None, False, 127, 0.02, 25),
    "tambourine":      (None, None, False, 127, 0.02, 25),
    # Synth
    "synth_lead":      (36, 96,  True,  18, 0.04, 20),
    "synth_pad":       (36, 96,  False, 18, 0.04, 20),
    "synth_bass":      (24, 60,  True,  12, 0.05, 20),
    # World
    "sitar":           (48, 84,  True,  14, 0.06, 30),
    "tabla":           (None, None, False, 127, 0.02, 30),
    "pan_flute":       (60, 96,  True,  12, 0.07, 35),
    "accordion":       (36, 91,  False, 18, 0.05, 35),
}

# Velocity floor by category if instrument not in INSTR_PROFILES
CATEGORY_FLOOR = {"brass": 50, "woodwind": 40, "strings": 35,
                  "keys": 20, "percussion": 25, "synth": 20}

QUANT_GRID = 0.05   # seconds — snap grid


def clean_midi(midi_path: str, output_path: str,
               instrument: str = "solo_cornet",
               mode: str = "solo") -> str:
    """
    Professional MIDI sanitization pipeline.
    Applies all global steps + mode-specific logic.
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    prof = INSTR_PROFILES.get(instrument)

    if prof:
        min_pitch, max_pitch, monophonic, max_jump, min_dur, vel_floor = prof
    else:
        min_pitch, max_pitch, monophonic, max_jump, min_dur, vel_floor = \
            21, 108, False, 24, 0.05, 30

    before = sum(len(i.notes) for i in pm.instruments)

    for instr in pm.instruments:
        notes = instr.notes

        # ── STEP 1: Noise removal ──────────────────────────────────────
        notes = [n for n in notes
                 if (n.end - n.start) >= min_dur and n.velocity >= 20]

        # ── STEP 2: Pitch range filtering (skip for unpitched) ─────────
        if min_pitch is not None:
            notes = [n for n in notes if min_pitch <= n.pitch <= max_pitch]

        # ── STEP 3: Sort by start time ─────────────────────────────────
        notes.sort(key=lambda n: n.start)

        # ── STEP 4: Remove exact duplicate pitches at same time ─────────
        seen, unique = set(), []
        for n in notes:
            key = (n.pitch, round(n.start, 3))
            if key not in seen:
                seen.add(key); unique.append(n)
        notes = unique

        # ── STEP 5: Timing quantization (snap to 0.05s grid) ───────────
        for n in notes:
            n.start = round(n.start / QUANT_GRID) * QUANT_GRID
            n.end   = max(n.start + min_dur, round(n.end / QUANT_GRID) * QUANT_GRID)

        notes.sort(key=lambda n: n.start)

        # ── STEP 6: Velocity gate (per instrument floor) ───────────────
        notes = [n for n in notes if n.velocity >= vel_floor]

        # ── STEP 7: Merge repeated same-pitch notes (gap < 0.05s) ──────
        merged = []
        for n in notes:
            if (merged and merged[-1].pitch == n.pitch
                    and (n.start - merged[-1].end) < 0.05):
                merged[-1].end = n.end
                merged[-1].velocity = max(merged[-1].velocity, n.velocity)
            else:
                merged.append(n)
        notes = merged

        # ── STEP 8: Remove unrealistic pitch jumps ─────────────────────
        if max_jump < 127:
            filtered, prev_pitch = [], None
            for n in notes:
                if prev_pitch is None or abs(n.pitch - prev_pitch) <= max_jump:
                    filtered.append(n); prev_pitch = n.pitch
            notes = filtered

        # ── STEP 9: Velocity smoothing (3-note sliding average) ────────
        notes = _smooth_velocity(notes)

        # ── STEP 10: Legato — close gaps by extending previous note ────
        for i in range(len(notes) - 1):
            gap = notes[i + 1].start - notes[i].end
            if 0 < gap < 0.05:
                notes[i].end = notes[i + 1].start

        # ── STEP 11: Mode-specific processing ─────────────────────────
        if monophonic or mode in ("solo", "vocal"):
            notes = _enforce_mono(notes, prefer="velocity")

        if mode == "vocal":
            notes = _vocal_process(notes)

        instr.notes = notes

    # ── Multi/Orchestra: split layers ─────────────────────────────────
    if mode in ("multi", "auto", "orchestra"):
        pm = _split_layers(pm, mode)

    pm.write(output_path)
    after = sum(len(i.notes) for i in pm.instruments)
    log.info(f"MIDI clean [{mode}/{instrument}]: {before} → {after} notes")
    return output_path


def _smooth_velocity(notes: list) -> list:
    """3-note local velocity averaging to reduce spikes."""
    if len(notes) < 3:
        return notes
    result = list(notes)
    for i in range(1, len(notes) - 1):
        avg = (notes[i-1].velocity + notes[i].velocity + notes[i+1].velocity) // 3
        result[i].velocity = max(20, min(127, avg))
    return result


def _enforce_mono(notes: list, prefer: str = "velocity") -> list:
    """
    Enforce monophonic playback — last-note-wins (most recent start).
    If two notes overlap, keep the one with higher velocity or pitch.
    """
    if not notes:
        return notes
    notes = sorted(notes, key=lambda n: n.start)
    mono = [notes[0]]
    for n in notes[1:]:
        prev = mono[-1]
        if n.start < prev.end:
            # Overlap — decide which to keep
            if prefer == "velocity":
                if n.velocity >= prev.velocity:
                    prev.end = n.start  # clip previous
                    mono.append(n)
                else:
                    pass  # discard new note
            else:  # prefer pitch
                if n.pitch >= prev.pitch:
                    prev.end = n.start
                    mono.append(n)
        else:
            mono.append(n)
    return mono


def _vocal_process(notes: list) -> list:
    """Vocal-specific: extend durations, limit jumps to 8 semitones, remove fast repeats."""
    if not notes:
        return notes
    # Remove fast repetitions — same pitch within 0.15s
    filtered = [notes[0]]
    for n in notes[1:]:
        prev = filtered[-1]
        if n.pitch == prev.pitch and (n.start - prev.start) < 0.15:
            continue
        filtered.append(n)
    # Limit pitch jumps to 8 semitones (vocal range)
    clean = [filtered[0]]
    for n in filtered[1:]:
        if abs(n.pitch - clean[-1].pitch) <= 8:
            clean.append(n)
    # Extend note durations — vocals sustain
    for i in range(len(clean) - 1):
        gap = clean[i + 1].start - clean[i].end
        if gap < 0.2:
            clean[i].end = clean[i + 1].start
    return clean


def _split_layers(pm: pretty_midi.PrettyMIDI, mode: str) -> pretty_midi.PrettyMIDI:
    """
    Split notes into melodic layers:
      multi/auto → melody, harmony, bass
      orchestra  → melody, harmony, bass, accents
    Returns a new PrettyMIDI with separate instruments per layer.
    """
    all_notes = []
    for instr in pm.instruments:
        if not instr.is_drum:
            all_notes.extend(instr.notes)
    if not all_notes:
        return pm

    all_notes.sort(key=lambda n: n.start)

    # Determine pitch split points
    pitches = sorted(n.pitch for n in all_notes)
    n_total = len(pitches)
    # Bass = bottom 25%, harmony = mid 50%, melody = top 25%
    bass_thresh    = pitches[max(0, n_total // 4)]
    treble_thresh  = pitches[min(n_total - 1, 3 * n_total // 4)]

    melody_notes   = [n for n in all_notes if n.pitch >= treble_thresh]
    harmony_notes  = [n for n in all_notes if bass_thresh <= n.pitch < treble_thresh]
    bass_notes     = [n for n in all_notes if n.pitch < bass_thresh]

    # For orchestra mode: accents = high-velocity short notes
    accent_notes   = []
    if mode == "orchestra":
        accent_notes = [n for n in all_notes
                        if n.velocity >= 100 and (n.end - n.start) < 0.2]

    # Build new PrettyMIDI with named tracks
    new_pm = pretty_midi.PrettyMIDI(initial_tempo=pm.estimate_tempo())
    layers = {"Melody": (melody_notes, 0), "Harmony": (harmony_notes, 0),
              "Bass": (bass_notes, 43)}
    if mode == "orchestra":
        layers["Accents"] = (accent_notes, 47)

    for name, (notes, prog) in layers.items():
        if not notes:
            continue
        instr = pretty_midi.Instrument(program=prog, name=name)
        instr.notes = list(notes)
        new_pm.instruments.append(instr)

    return new_pm
