"""
utils/humanizer.py — SoundToScore V14
=======================================
Studio-quality MIDI humanization engine.

Applies:
  1. Timing jitter — ±5ms random offset (simulates human imprecision)
  2. Velocity variation — ±8 random variation per note
  3. Phrase-level velocity shaping — crescendo / decrescendo across phrases
  4. Micro-agogics — slight delays on phrase peaks (expressive timing)
  5. Category-specific behaviour:
       Brass  — stronger attack, less timing jitter
       Strings— more timing flexibility, softer attacks
       Keys   — tight timing, wide velocity range
       Winds  — legato feel, gentle dynamics
"""
import random, logging, math
from pathlib import Path
import pretty_midi

log = logging.getLogger("soundtoscore")

# Category-specific jitter/velocity parameters
CATEGORY_PARAMS = {
    "brass":      {"jitter": 0.008, "vel_range": 8,  "attack_boost": 1.05},
    "woodwind":   {"jitter": 0.010, "vel_range": 8,  "attack_boost": 1.02},
    "strings":    {"jitter": 0.015, "vel_range": 10, "attack_boost": 0.95},
    "keys":       {"jitter": 0.005, "vel_range": 12, "attack_boost": 1.0},
    "percussion": {"jitter": 0.004, "vel_range": 10, "attack_boost": 1.0},
    "synth":      {"jitter": 0.005, "vel_range": 6,  "attack_boost": 1.0},
    "default":    {"jitter": 0.012, "vel_range": 8,  "attack_boost": 1.0},
}

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


def humanize_midi(midi_path: str, output_path: str,
                  instrument: str = "solo_cornet",
                  seed: int = 42) -> str:
    """
    Apply studio-quality human-feel variation to MIDI notes.
    seed=42 ensures reproducible output for the same input.
    """
    pm = pretty_midi.PrettyMIDI(midi_path)
    cat = INSTR_CATEGORY.get(instrument, "default")
    params = CATEGORY_PARAMS.get(cat, CATEGORY_PARAMS["default"])
    rng = random.Random(seed)

    jitter     = params["jitter"]
    vel_range  = params["vel_range"]
    atk_boost  = params["attack_boost"]

    for instr in pm.instruments:
        if instr.is_drum:
            continue

        notes = sorted(instr.notes, key=lambda n: n.start)
        if not notes:
            continue

        # ── Phrase detection: split into 16-note phrases ───────────────
        phrase_len = 16
        phrases = [notes[i:i+phrase_len] for i in range(0, len(notes), phrase_len)]

        all_notes = []
        for p_idx, phrase in enumerate(phrases):
            # Alternate crescendo / decrescendo per phrase
            direction = 1 if p_idx % 2 == 0 else -1

            for i, note in enumerate(phrase):
                # ── Timing jitter ──────────────────────────────────────
                t_jitter = rng.uniform(-jitter, jitter)
                note.start = max(0.0, note.start + t_jitter)
                note.end   = max(note.start + 0.04, note.end + t_jitter * 0.4)

                # ── Phrase velocity shaping ────────────────────────────
                phrase_pos = i / max(len(phrase) - 1, 1)
                # Crescendo first half, decrescendo second (or reverse)
                shape = math.sin(math.pi * phrase_pos)
                phrase_factor = 1.0 + direction * 0.12 * shape

                # ── Random velocity variation ──────────────────────────
                vel_shift = rng.randint(-vel_range // 2, vel_range // 2)

                # ── Attack boost (category-specific) ──────────────────
                # First note of phrase gets a slight accent
                boost = atk_boost if i == 0 else 1.0

                final_vel = int(note.velocity * phrase_factor * boost) + vel_shift
                note.velocity = max(20, min(127, final_vel))

                # ── Micro-agogics: slightly delay phrase peak ──────────
                if i == len(phrase) // 2:
                    note.start = min(note.start + 0.004, note.end - 0.04)

                all_notes.append(note)

        instr.notes = all_notes

    pm.write(output_path)
    log.info(f"Humanized MIDI [{cat}] -> {output_path}")
    return output_path
