"""
services/merger.py — SoundToScore V14
======================================
After all chunks complete, merges them into one final output:
  - Full merged MIDI (all chunk MIDIs concatenated, time-offset corrected)
  - Full merged MIDI → clean again → enhance again (double pass quality)
  - Full merged MIDI → synthesize → effects → final WAV
  - Full transcript (all chunk transcripts concatenated)

This gives the user both per-chunk previews AND a polished full version.
"""
import logging, subprocess, shutil
from pathlib import Path
import pretty_midi

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INSTRUMENT_CONFIG, CHUNK_SEC
from utils.midi_cleaner   import clean_midi
from utils.midi_enhancer  import enhance_midi
from utils.transpose      import transpose_midi
from utils.instrument_map import set_instrument_program
from utils.synth          import synthesize
from utils.effects        import apply_effects
from utils.transcript     import generate_transcript

log = logging.getLogger("soundtoscore")


def merge_chunks(job_dir: str, chunk_results: list,
                 instrument: str, tempo: int, output_fmt: str,
                 sf2: str) -> dict:
    """
    Merge all chunk MIDI files into one polished full output.

    chunk_results: list of dicts from process_chunk()
    Returns: {
        "merged_midi":       filename,
        "merged_audio":      filename,
        "merged_transcript": filename,
        "merged_sheet":      filename or None,
    }
    All paths relative to job_dir/merged/
    """
    job_dir = Path(job_dir)
    out     = job_dir / "merged"
    out.mkdir(exist_ok=True)

    log.info(f"[merge] Merging {len(chunk_results)} chunks...")

    # ── 1. Concatenate all chunk MIDI files ────────────────
    raw_merged = str(out / "01_raw_merged.mid")
    _concat_midis(chunk_results, raw_merged, tempo=tempo)

    # ── 2. Clean the full merged MIDI (removes any artefacts at boundaries) ──
    clean_merged = str(out / "02_clean_merged.mid")
    clean_midi(raw_merged, clean_merged)

    # ── 3. Enhance the full MIDI (quantize across full duration) ─
    enhanced_merged = str(out / "03_enhanced_merged.mid")
    enhance_midi(clean_merged, enhanced_merged)

    # ── 4. Instrument map + transpose ─────────────────────
    _, semitones = INSTRUMENT_CONFIG.get(instrument, (0, 0))

    mapped_merged = str(out / "04_mapped_merged.mid")
    set_instrument_program(enhanced_merged, mapped_merged, instrument)

    final_merged_midi = str(out / "merged.mid")
    transpose_midi(mapped_merged, final_merged_midi, semitones=semitones)

    # ── 5. Synthesize full merged MIDI ────────────────────
    dry_merged = str(out / "05_dry_merged.wav")
    synthesize(final_merged_midi, dry_merged, sf2)

    # ── 6. Apply effects to full merged audio ─────────────
    final_wav = str(out / "merged.wav")
    apply_effects(dry_merged, final_wav)

    # ── 7. Convert to MP3 if requested ────────────────────
    audio_filename = "merged.wav"
    if output_fmt == "mp3":
        final_mp3 = str(out / "merged.mp3")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", final_wav,
             "-acodec", "libmp3lame", "-q:a", "4", final_mp3],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0 and Path(final_mp3).exists():
            audio_filename = "merged.mp3"

    # ── 8. Full transcript ────────────────────────────────
    txt = generate_transcript(final_merged_midi, str(out / "merged_notes.txt"), tempo=tempo)

    # ── 9. Sheet music (best-effort) ─────────────────────
    sheet_filename = None
    try:
        from utils.sheet import generate_sheet
        ok = generate_sheet(final_merged_midi, str(out / "merged_sheet.pdf"),
                            title="Full Score")
        if ok and (out / "merged_sheet.pdf").exists():
            sheet_filename = "merged_sheet.pdf"
    except Exception as e:
        log.warning(f"[merge] Sheet failed: {e}")

    log.info(f"[merge] Done → {audio_filename}")
    return {
        "merged_midi":       "merged.mid",
        "merged_audio":      audio_filename,
        "merged_transcript": "merged_notes.txt",
        "merged_sheet":      sheet_filename,
        "merged_preview":    (txt or "")[:600],
    }


def _concat_midis(chunk_results: list, output_path: str, tempo: int = 120):
    """
    Concatenate MIDI from each chunk, correctly time-offsetting each one
    so they play in sequence (chunk 1 starts at 0s, chunk 2 at 20s, etc.).
    """
    pm_out = pretty_midi.PrettyMIDI(initial_tempo=float(tempo))
    instr_out = pretty_midi.Instrument(program=0)

    for cr in chunk_results:
        chunk_idx  = cr.get("chunk", 1)
        # Time offset: each chunk is CHUNK_SEC seconds apart
        t_offset   = (chunk_idx - 1) * CHUNK_SEC
        midi_path  = cr.get("_abs_midi_path")    # set by app.py

        if not midi_path or not Path(midi_path).exists():
            log.warning(f"[merge] Missing MIDI for chunk {chunk_idx}: {midi_path}")
            continue

        try:
            pm_chunk = pretty_midi.PrettyMIDI(midi_path)
            for instr in pm_chunk.instruments:
                for note in instr.notes:
                    # Offset note times by chunk position
                    new_note = pretty_midi.Note(
                        velocity=note.velocity,
                        pitch=note.pitch,
                        start=note.start + t_offset,
                        end=note.end   + t_offset,
                    )
                    instr_out.notes.append(new_note)
        except Exception as e:
            log.warning(f"[merge] Skipping chunk {chunk_idx} MIDI: {e}")

    instr_out.notes.sort(key=lambda n: n.start)
    pm_out.instruments.append(instr_out)
    pm_out.write(output_path)
    log.info(f"[merge] Concatenated {len(chunk_results)} chunks → {output_path}")
