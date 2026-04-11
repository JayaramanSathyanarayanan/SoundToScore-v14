"""
services/midi_pipeline.py — SoundToScore V14
=============================================
Full per-chunk MIDI pipeline. Mode-aware processing:

  solo / instrument → monophonic, instrument-strict
  vocal             → strict mono, extended durations, limited jumps
  multi / auto      → melody + harmony + bass split
  orchestra         → melody + harmony + bass + accents

Pipeline stages:
  WAV → extract → sanitize (clean) → enhance → humanize
      → instrument map → transpose → synthesize → effects → transcript
"""
import logging, subprocess
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INSTRUMENT_CONFIG
from utils.midi_processing import extract_midi
from utils.midi_cleaner    import clean_midi
from utils.midi_enhancer   import enhance_midi
from utils.humanizer       import humanize_midi
from utils.transpose       import transpose_midi
from utils.instrument_map  import set_instrument_program
from utils.synth           import synthesize
from utils.effects         import apply_effects
from utils.transcript      import generate_transcript
from utils.sheet           import generate_sheet

log = logging.getLogger("soundtoscore")


def process_chunk(chunk_wav: str, out_dir: str,
                  instrument: str, tempo: int, output_fmt: str,
                  sf2: str, chunk_title: str = "Section",
                  mode: str = "auto") -> dict:
    """
    Full pipeline for one 20-second audio chunk.
    mode: 'auto' | 'solo' | 'vocal' | 'multi' | 'orchestra'

    Returns {midi_file, audio_file, transcript_file, sheet_file,
             transcript_preview, clean_midi_path}
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)

    _, semitones = INSTRUMENT_CONFIG.get(instrument, (0, 0))

    # ── Step 1: Extract raw MIDI via librosa YIN ───────────────────────
    raw_midi = str(d / "01_raw.mid")
    extract_midi(chunk_wav, raw_midi, sr=16000, tempo=tempo)

    # ── Step 2: Professional sanitization ─────────────────────────────
    # Applies: noise removal, pitch range, dedup, jump filter,
    # quantization, velocity gate, merge repeats, legato, mono enforce
    clean = str(d / "02_clean.mid")
    clean_midi(raw_midi, clean, instrument=instrument, mode=mode)

    # ── Step 3: Studio enhancement ────────────────────────────────────
    # Applies: fine quantization, phrase velocity shaping, normalization,
    # articulation, breath model
    enhanced = str(d / "03_enhanced.mid")
    enhance_midi(clean, enhanced, instrument=instrument, mode=mode)

    # ── Step 4: Humanization ──────────────────────────────────────────
    # Applies: timing jitter, velocity variation, phrase dynamics,
    # micro-agogics, attack shaping
    human = str(d / "04_human.mid")
    humanize_midi(enhanced, human, instrument=instrument)

    # ── Step 5: MIDI program assignment ───────────────────────────────
    mapped = str(d / "05_mapped.mid")
    set_instrument_program(human, mapped, instrument)

    # ── Step 6: Semitone transposition (Bb/Eb key correction) ─────────
    final_midi = str(d / "out.mid")
    transpose_midi(mapped, final_midi, semitones=semitones)

    # ── Step 7: FluidSynth synthesis ──────────────────────────────────
    dry_wav = str(d / "07_dry.wav")   # temp — not served
    synthesize(final_midi, dry_wav, sf2)

    # ── Step 8: Effects (reverb + EQ + loudnorm) ──────────────────────
    final_wav = str(d / "out.wav")
    apply_effects(dry_wav, final_wav)

    # ── Step 9: Optional MP3 conversion ───────────────────────────────
    audio_filename = "out.wav"
    if output_fmt == "mp3":
        final_mp3 = str(d / "out.mp3")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", final_wav,
             "-acodec", "libmp3lame", "-q:a", "4", final_mp3],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0 and Path(final_mp3).exists():
            audio_filename = "out.mp3"

    # ── Step 10: Transcript ────────────────────────────────────────────
    txt = generate_transcript(final_midi, str(d / "notes.txt"), tempo=tempo)

    # ── Step 11: Sheet music (best-effort — needs MuseScore) ──────────
    sheet_filename = None
    sheet_ok = generate_sheet(final_midi, str(d / "sheet.pdf"), title=chunk_title)
    if sheet_ok and (d / "sheet.pdf").exists():
        sheet_filename = "sheet.pdf"

    log.info(f"Chunk done [{chunk_title}] mode={mode} instr={instrument} → {audio_filename}")
    return {
        "midi_file":          "out.mid",
        "audio_file":         audio_filename,
        "transcript_file":    "notes.txt",
        "sheet_file":         sheet_filename,
        "transcript_preview": (txt or "")[:400],
        "clean_midi_path":    clean,   # used by merger
    }
