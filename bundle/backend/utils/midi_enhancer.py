"""
utils/midi_enhancer.py — SoundToScore V14
==========================================
Studio-quality MIDI enhancement engine.

Steps applied:
  1. Fine-grid quantization (1/16th note = 0.125s at 120 BPM)
  2. Velocity curve — sinusoidal phrase shaping per 16-note phrase
  3. Articulation shaping — staccato (short), legato (long), normal
  4. Merge near-identical notes (same pitch, gap < 0.05s)
  5. Dynamic range normalization — compress extremes gently
  6. Breath model for wind instruments — natural phrase breaks
"""
import logging, math
from pathlib import Path
import pretty_midi

log = logging.getLogger("soundtoscore")

# Quantization grid sizes by instrument category
GRID_BY_CATEGORY = {
    "brass":      0.0625,   # 1/16 note
    "woodwind":   0.0625,
    "strings":    0.05,     # slightly finer for strings
    "keys":       0.0417,   # 1/24 (triplet feel) for piano
    "percussion": 0.03125,  # tight 1/32 for percussion
    "synth":      0.05,
    "default":    0.0625,
}

# Instrument → category
INSTR_CATEGORY = {
    "soprano_cornet":"brass","solo_cornet":"brass","repiano_cornet":"brass",
    "cornet_2nd":"brass","cornet_3rd":"brass","flugelhorn":"brass",
    "solo_tenor_horn":"brass","tenor_horn_1st":"brass","tenor_horn_2nd":"brass",
    "baritone_1st":"brass","baritone_2nd":"brass","euphonium":"brass",
    "trombone_1st":"brass","trombone_2nd":"brass","bass_trombone":"brass",
    "eb_bass":"brass","bbb_bass":"brass","trumpet_bb":"brass","trumpet_c":"brass",
    "trumpet_d":"brass","trumpet_eb":"brass","piccolo_trumpet":"brass",
    "pocket_trumpet":"brass","muted_trumpet":"brass","harmon_trumpet":"brass",
    "french_horn":"brass","tenor_horn":"brass","baritone":"brass","tuba":"brass",
    "concert_grand":"keys","baby_grand":"keys","upright":"keys","studio_piano":"keys",
    "honky_tonk":"keys","felt_piano":"keys","prepared_piano":"keys",
    "rhodes":"keys","wurlitzer":"keys","fm_piano":"keys","accordion":"keys",
    "violin":"strings","viola":"strings","cello":"strings","double_bass":"strings",
    "string_ensemble":"strings","pizzicato":"strings","tremolo":"strings","staccato":"strings",
    "acoustic_guitar":"strings","electric_guitar":"strings","distortion_guitar":"strings",
    "electric_bass":"strings","slap_bass":"strings","sitar":"strings",
    "flute":"woodwind","piccolo":"woodwind","alto_flute":"woodwind",
    "clarinet":"woodwind","bass_clarinet":"woodwind","oboe":"woodwind",
    "bassoon":"woodwind","alto_sax":"woodwind","tenor_sax":"woodwind",
    "baritone_sax":"woodwind","pan_flute":"woodwind",
    "timpani":"percussion","glockenspiel":"percussion","xylophone":"percussion",
    "tubular_bells":"percussion","drum_kit":"percussion","snare_drum":"percussion",
    "bass_drum":"percussion","cymbals":"percussion","triangle":"percussion",
    "tambourine":"percussion","tabla":"percussion",
    "synth_lead":"synth","synth_pad":"synth","synth_bass":"synth",
}


def enhance_midi(midi_path: str, output_path: str,
                 instrument: str = "solo_cornet",
                 mode: str = "solo") -> str:
    """
    Studio-quality enhancement pass.
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    cat = INSTR_CATEGORY.get(instrument, "default")
    grid = GRID_BY_CATEGORY.get(cat, GRID_BY_CATEGORY["default"])

    for instr in pm.instruments:
        if instr.is_drum:
            continue

        notes = sorted(instr.notes, key=lambda n: n.start)
        if not notes:
            continue

        # ── 1. Quantize timing to grid ─────────────────────────────────
        for n in notes:
            n.start = round(n.start / grid) * grid
            n.end   = max(n.start + 0.04, round(n.end / grid) * grid)

        notes.sort(key=lambda n: n.start)

        # ── 2. Merge near-identical notes ─────────────────────────────
        merged = [notes[0]]
        for n in notes[1:]:
            prev = merged[-1]
            if prev.pitch == n.pitch and (n.start - prev.end) < 0.05:
                prev.end = n.end
                prev.velocity = max(prev.velocity, n.velocity)
            else:
                merged.append(n)
        notes = merged

        # ── 3. Phrase velocity shaping (16-note phrases) ───────────────
        notes = _shape_phrase_velocity(notes, cat)

        # ── 4. Dynamic range normalization ─────────────────────────────
        notes = _normalize_dynamics(notes)

        # ── 5. Articulation — duration shaping ─────────────────────────
        notes = _shape_articulation(notes, cat)

        # ── 6. Breath model for wind instruments ───────────────────────
        if cat in ("brass", "woodwind"):
            notes = _apply_breath_model(notes)

        instr.notes = notes

    pm.write(output_path)
    log.info(f"MIDI enhanced [{cat}] -> {output_path}")
    return output_path


def _shape_phrase_velocity(notes: list, category: str) -> list:
    """
    Apply sinusoidal velocity envelope across 16-note phrases.
    Louder in the middle of each phrase, softer at the edges.
    """
    PHRASE_LEN = 16
    result = list(notes)
    for i, n in enumerate(result):
        phrase_pos = (i % PHRASE_LEN) / (PHRASE_LEN - 1)
        # sin curve: quiet at start/end, louder in middle
        envelope = 0.75 + 0.25 * math.sin(math.pi * phrase_pos)
        result[i].velocity = max(20, min(127, int(n.velocity * envelope)))
    return result


def _normalize_dynamics(notes: list) -> list:
    """
    Soft compression: bring extremes closer to the median.
    Prevents both inaudibly quiet and ear-splitting loud notes.
    """
    if not notes:
        return notes
    vels = sorted(n.velocity for n in notes)
    median = vels[len(vels) // 2]
    result = list(notes)
    for n in result:
        diff = n.velocity - median
        # Compress by 20%
        n.velocity = max(20, min(127, median + int(diff * 0.8)))
    return result


def _shape_articulation(notes: list, category: str) -> list:
    """
    Shape note durations based on instrument category.
    Brass/woodwind: slightly detached (0.85x duration gap)
    Strings: legato (extend to next note)
    Piano: natural decay
    """
    if len(notes) < 2:
        return notes
    result = list(notes)
    for i in range(len(result) - 1):
        curr = result[i]
        nxt  = result[i + 1]
        natural_dur = curr.end - curr.start

        if category in ("brass", "woodwind"):
            # Detached: clip note to 85% of space before next
            max_end = curr.start + (nxt.start - curr.start) * 0.85
            curr.end = min(curr.end, max_end)
            curr.end = max(curr.end, curr.start + natural_dur * 0.6)

        elif category == "strings":
            # Legato: extend to next note start
            if nxt.start - curr.end < 0.08:
                curr.end = nxt.start

        elif category == "keys":
            # Piano: natural release — 80% of duration or until next note
            curr.end = min(curr.end, curr.start + natural_dur * 0.9)

    return result


def _apply_breath_model(notes: list) -> list:
    """
    Wind instrument breath model:
    Insert a natural silence every 8-12 notes to simulate breathing.
    Shorten the last note before a phrase break slightly.
    """
    if len(notes) < 8:
        return notes
    PHRASE_LEN = 10  # notes per breath
    result = list(notes)
    for i in range(PHRASE_LEN - 1, len(result) - 1, PHRASE_LEN):
        # Shorten the last note of each phrase by 15%
        dur = result[i].end - result[i].start
        result[i].end = result[i].start + dur * 0.85
    return result
