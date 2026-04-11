"""
services/merger.py — SoundToScore V14
======================================
Merges all chunks into one polished full output.
Applies clean + enhance (double pass) to full merged MIDI.
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
                 sf2: str, mode: str = "auto") -> dict:
    """
    Merge all chunk MIDI files into one polished full output.
    Returns {merged_midi, merged_audio, merged_transcript, merged_sheet, merged_preview}
    All paths relative to job_dir/merged/
    """
    job_dir = Path(job_dir)
    out     = job_dir / "merged"
    out.mkdir(exist_ok=True)

    log.info(f"[merge] Merging {len(chunk_results)} chunks, mode={mode}, instr={instrument}")

    # ── 1. Concatenate all chunk MIDIs with time offsets ──────────────
    raw_merged = str(out / "01_raw_merged.mid")
    _concat_midis(chunk_results, raw_merged, tempo=tempo)

    # ── 2. Professional sanitization on full merged MIDI ─────────────
    clean_merged = str(out / "02_clean_merged.mid")
    clean_midi(raw_merged, clean_merged, instrument=instrument, mode=mode)

    # ── 3. Studio enhancement on full MIDI ───────────────────────────
    enhanced_merged = str(out / "03_enhanced_merged.mid")
    enhance_midi(clean_merged, enhanced_merged, instrument=instrument, mode=mode)

    # ── 4. Instrument map + transpose ────────────────────────────────
    _, semitones = INSTRUMENT_CONFIG.get(instrument, (0, 0))
    mapped_merged = str(out / "04_mapped_merged.mid")
    set_instrument_program(enhanced_merged, mapped_merged, instrument)

    final_merged_midi = str(out / "merged.mid")
    transpose_midi(mapped_merged, final_merged_midi, semitones=semitones)

    # ── 5. Synthesize ─────────────────────────────────────────────────
    dry_merged = str(out / "05_dry_merged.wav")
    synthesize(final_merged_midi, dry_merged, sf2)

    # ── 6. Effects ───────────────────────────────────────────────────
    final_wav = str(out / "merged.wav")
    apply_effects(dry_merged, final_wav)

    # ── 7. MP3 if requested ──────────────────────────────────────────
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

    # ── 8. Transcript ─────────────────────────────────────────────────
    txt = generate_transcript(final_merged_midi, str(out / "merged_notes.txt"), tempo=tempo)

    # ── 9. Sheet music (best-effort) ──────────────────────────────────
    sheet_filename = None
    try:
        from utils.sheet import generate_sheet
        ok = generate_sheet(final_merged_midi, str(out / "merged_sheet.pdf"), title="Full Score")
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
    Concatenate chunk MIDIs with correct time offsets.
    Each chunk is offset by (chunk_idx - 1) * CHUNK_SEC seconds.
    """
    pm_out = pretty_midi.PrettyMIDI(initial_tempo=float(tempo))
    instr_out = pretty_midi.Instrument(program=0, name="Main")

    for cr in chunk_results:
        chunk_idx = cr.get("chunk", 1)
        t_offset  = (chunk_idx - 1) * CHUNK_SEC
        midi_path = cr.get("_abs_midi_path")

        if not midi_path or not Path(midi_path).exists():
            log.warning(f"[merge] Missing MIDI for chunk {chunk_idx}")
            continue

        try:
            pm_chunk = pretty_midi.PrettyMIDI(midi_path)
            for instr in pm_chunk.instruments:
                if not instr.is_drum:
                    for note in instr.notes:
                        instr_out.notes.append(pretty_midi.Note(
                            velocity=note.velocity,
                            pitch=note.pitch,
                            start=note.start + t_offset,
                            end=note.end   + t_offset,
                        ))
        except Exception as e:
            log.warning(f"[merge] Skipping chunk {chunk_idx}: {e}")

    instr_out.notes.sort(key=lambda n: n.start)
    pm_out.instruments.append(instr_out)
    pm_out.write(output_path)
    log.info(f"[merge] Concatenated {len(chunk_results)} chunks → {output_path}")
