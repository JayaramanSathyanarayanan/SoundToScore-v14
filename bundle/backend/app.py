"""
SoundToScore V14 — FastAPI Backend
====================================
Flow:
  POST /api/convert  → {job_id} immediately (non-blocking)
  Background thread:
    1. Preprocess audio
    2. (Optional) Stem separation
    3. Smart stem selection
    4. Split into 20s chunks
    5. For each chunk → full pipeline → save to meta.json immediately
       (frontend polls and shows each chunk as it completes ← STREAMING)
    6. After ALL chunks done → merge into one full output
       (clean + enhance applied again to full merge ← QUALITY)
    7. Mark status=success

  GET /api/status/{job_id}  → {status, chunks[], merged, ...}
  GET /api/files/{job_id}/{section}/{filename} → serve files
  GET /api/merged/{job_id}/{filename}          → serve merged files

Deployment:
  Backend → Render (free tier, 512MB RAM, 2 workers max)
  Frontend → Vercel (static, calls API via CORS)
"""

import uuid, shutil, time, logging, json, threading
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import (
    UPLOAD_DIR, OUTPUT_DIR,
    MAX_BYTES, MAX_CONCURRENT_JOBS, JOB_TTL,
    VALID_INSTRUMENTS, INSTRUMENT_CONFIG, SF_FILE,
)
from utils.soundfont        import ensure_soundfont
from utils.preprocess       import preprocess_audio
from utils.demucs_separate  import separate_stems
from utils.auto_select      import select_best_stem
from utils.chunking         import split_into_chunks
from services.midi_pipeline import process_chunk
from services.merger        import merge_chunks
from services.optimization  import decide_pipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("soundtoscore")

app = FastAPI(title="SoundToScore V14", version="14.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════
# META — disk-persisted checkpoint (survives server restart)
# ══════════════════════════════════════════════════════════

def _meta_path(job_id: str) -> Path:
    return OUTPUT_DIR / job_id / "meta.json"

def _read_meta(job_id: str) -> dict:
    p = _meta_path(job_id)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}

def _write_meta(job_id: str, meta: dict):
    path = _meta_path(job_id)
    tmp  = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=2)
    tmp.replace(path)   # atomic — never corrupted

def _update_meta(job_id: str, **kw):
    m = _read_meta(job_id)
    m.update(kw)
    _write_meta(job_id, m)

# ══════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    log.info("SoundToScore V14 starting...")
    # Mark any jobs interrupted by restart as failed
    if OUTPUT_DIR.exists():
        for d in OUTPUT_DIR.iterdir():
            mf = d / "meta.json"
            if mf.exists():
                try:
                    m = json.loads(mf.read_text())
                    if m.get("status") == "processing":
                        log.warning(f"[{d.name}] Interrupted — marking failed")
                        _update_meta(d.name, status="failed",
                                     error="Server restarted — please re-upload.")
                except Exception:
                    pass
    try:
        ensure_soundfont()
        log.info("SoundFont ready.")
    except Exception as e:
        log.error(f"SoundFont startup error: {e}")

# ══════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "SoundToScore V14 running",
            "version": "14.0.0",
            "soundfont": SF_FILE.exists()}

@app.get("/api/health")
def health():
    return {"ok": True, "soundfont_ready": SF_FILE.exists()}

# ══════════════════════════════════════════════════════════
# CONVERT — returns job_id immediately, never blocks request
# ══════════════════════════════════════════════════════════

@app.post("/api/convert")
async def convert(
    background:   BackgroundTasks,
    file:         UploadFile = File(...),
    instrument:   str        = Form("solo_cornet"),
    mode:         str        = Form("auto"),      # auto | vocal | instrument
    tempo:        int        = Form(120),
    output_fmt:   str        = Form("wav"),
):
    # Validate
    if instrument not in VALID_INSTRUMENTS:
        raise HTTPException(400, f"Unknown instrument: {instrument}")
    if mode not in {"auto", "vocal", "instrument"}:
        raise HTTPException(400, f"Invalid mode: {mode}")
    ext = Path(file.filename or "upload").suffix.lower()
    if ext not in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 100 MB)")

    # Concurrency guard — Render free tier: max 2 jobs
    active = 0
    if OUTPUT_DIR.exists():
        for d in OUTPUT_DIR.iterdir():
            mf = d / "meta.json"
            if mf.exists():
                try:
                    if json.loads(mf.read_text()).get("status") == "processing":
                        active += 1
                except Exception:
                    pass
    if active >= MAX_CONCURRENT_JOBS:
        raise HTTPException(503, "Server busy — please try again in a moment.")

    # Create job
    job_id  = uuid.uuid4().hex[:10]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True)

    src = UPLOAD_DIR / f"{job_id}{ext}"
    src.write_bytes(data)

    quality_warning = ("Low-quality audio — accuracy may be reduced."
                       if len(data) < 300_000 else None)

    _write_meta(job_id, {
        "job_id":          job_id,
        "status":          "processing",
        "instrument":      instrument,
        "mode":            mode,
        "tempo":           tempo,
        "output_fmt":      output_fmt,
        "quality_warning": quality_warning,
        "total_chunks":    0,
        "done_chunks":     0,
        "chunks":          [],      # filled as each chunk completes
        "merged":          None,    # filled after all chunks done
        "error":           None,
        "elapsed":         0,
        "duration":        0,
        "phase":           "uploading",
        "created_at":      time.time(),
    })

    log.info(f"[{job_id}] Job created — {len(data)//1024}KB inst={instrument} mode={mode}")

    # Non-blocking background thread
    background.add_task(_launch, job_id, str(src), instrument, mode, tempo, output_fmt)

    return JSONResponse({"job_id": job_id, "status": "processing"})


def _launch(job_id, src, inst, mode, tempo, fmt):
    threading.Thread(
        target=_pipeline,
        args=(job_id, src, inst, mode, tempo, fmt),
        daemon=True
    ).start()

# ══════════════════════════════════════════════════════════
# PIPELINE — background thread
# ══════════════════════════════════════════════════════════

def _pipeline(job_id, src_path, instrument, mode, tempo, output_fmt):
    import librosa
    job_dir = OUTPUT_DIR / job_id
    t0      = time.time()
    log.info(f"[{job_id}] Pipeline started in thread")

    try:
        sf2 = ensure_soundfont()

        # ── Phase 1: Preprocess ────────────────────────────
        _update_meta(job_id, phase="preprocessing")
        pre = str(job_dir / "preprocessed.wav")
        preprocess_audio(src_path, pre, sr=16000)
        Path(src_path).unlink(missing_ok=True)

        dur       = librosa.get_duration(path=pre)
        file_size = Path(pre).stat().st_size
        plan      = decide_pipeline(file_size, dur)
        _update_meta(job_id, duration=round(dur, 1))

        # ── Phase 2: Stem separation ───────────────────────
        _update_meta(job_id, phase="separating_stems")
        if plan["use_demucs"]:
            stems = separate_stems(pre, str(job_dir / "stems"))
        else:
            log.info(f"[{job_id}] Skipping demucs")
            stems = {"other": pre, "vocals": pre, "bass": pre, "drums": pre}

        selected = select_best_stem(stems, mode=mode)
        log.info(f"[{job_id}] Selected stem: {selected}")

        # ── Phase 3: Chunk ─────────────────────────────────
        _update_meta(job_id, phase="chunking")
        chunk_metas = split_into_chunks(selected, str(job_dir / "chunk_audio"), sr=16000)
        n_ch        = min(len(chunk_metas), plan["max_chunks"])
        _update_meta(job_id, total_chunks=n_ch, phase="converting")

        # Resume: skip already-done chunks
        existing = _read_meta(job_id)
        done_set = {c["chunk"] for c in existing.get("chunks", [])}

        # ── Phase 4: Process each chunk ────────────────────
        # Keep track of chunk outputs for merge step
        chunk_outputs_for_merge = []

        for ci in chunk_metas[:n_ch]:
            idx  = ci["index"]
            cst  = ci["start"]
            cen  = ci["end"]
            cwav = ci["path"]

            if idx in done_set:
                # Re-collect paths for merge even if chunk was already done
                abs_midi = str(job_dir / f"s{idx}" / "out.mid")
                chunk_outputs_for_merge.append({
                    "chunk": idx, "_abs_midi_path": abs_midi
                })
                log.info(f"[{job_id}] Chunk {idx} already done — skipping")
                continue

            out_dir = str(job_dir / f"s{idx}")
            outputs = process_chunk(
                cwav, out_dir, instrument, tempo, output_fmt, sf2,
                chunk_title=f"Section {idx}"
            )

            # Absolute path to the final MIDI for this chunk (used by merger)
            abs_midi = str(job_dir / f"s{idx}" / outputs["midi_file"])

            chunk_outputs_for_merge.append({
                "chunk":           idx,
                "_abs_midi_path":  abs_midi,
            })

            # Build URL paths (relative to API root)
            base = f"/api/files/{job_id}/s{idx}"
            chunk_result = {
                "chunk":              idx,
                "start":              cst,
                "end":                cen,
                "audio":      f"{base}/{outputs['audio_file']}",
                "midi":       f"{base}/{outputs['midi_file']}",
                "transcript": f"{base}/{outputs['transcript_file']}",
                "sheet":      f"{base}/{outputs['sheet_file']}" if outputs.get("sheet_file") else None,
                "transcript_preview": outputs["transcript_preview"],
            }

            # ✅ Write to meta immediately → frontend gets it on next poll
            meta        = _read_meta(job_id)
            chunks_list = meta.get("chunks", [])
            chunks_list.append(chunk_result)
            meta.update({
                "chunks":      chunks_list,
                "done_chunks": len(chunks_list),
                "elapsed":     round(time.time() - t0, 2),
                "phase":       f"chunk_{idx}_of_{n_ch}",
            })
            _write_meta(job_id, meta)
            log.info(f"[{job_id}] ✓ Chunk {idx}/{n_ch} streamed to frontend")

        # ── Phase 5: Merge all chunks → full output ────────
        _update_meta(job_id, phase="merging")
        log.info(f"[{job_id}] Merging {len(chunk_outputs_for_merge)} chunks...")

        merged_out = None
        try:
            merged_out = merge_chunks(
                str(job_dir),
                chunk_outputs_for_merge,
                instrument=instrument,
                tempo=tempo,
                output_fmt=output_fmt,
                sf2=sf2,
            )
            # Build URL paths for merged files
            mbase = f"/api/merged/{job_id}"
            merged_result = {
                "audio":      f"{mbase}/{merged_out['merged_audio']}",
                "midi":       f"{mbase}/{merged_out['merged_midi']}",
                "transcript": f"{mbase}/{merged_out['merged_transcript']}",
                "sheet":      f"{mbase}/{merged_out['merged_sheet']}" if merged_out.get("merged_sheet") else None,
                "preview":    merged_out.get("merged_preview", ""),
            }
            log.info(f"[{job_id}] ✓ Merged output ready")
        except Exception as me:
            log.error(f"[{job_id}] Merge failed (non-fatal): {me}")
            merged_result = None

        # ── Phase 6: Done ──────────────────────────────────
        _update_meta(job_id,
                     status="success",
                     phase="done",
                     elapsed=round(time.time() - t0, 2),
                     merged=merged_result)
        log.info(f"[{job_id}] All done in {time.time()-t0:.1f}s")

        # Cleanup after TTL
        def _cleanup():
            time.sleep(JOB_TTL)
            shutil.rmtree(str(job_dir), ignore_errors=True)
            log.info(f"[{job_id}] Cleaned up")
        threading.Thread(target=_cleanup, daemon=True).start()

    except Exception as exc:
        import traceback
        log.error(f"[{job_id}] FAILED: {exc}\n{traceback.format_exc()}")
        _update_meta(job_id, status="failed", error=str(exc), phase="failed")
        Path(src_path).unlink(missing_ok=True)

# ══════════════════════════════════════════════════════════
# STATUS — polled every 5s by frontend
# ══════════════════════════════════════════════════════════

@app.get("/api/status/{job_id}")
def status(job_id: str):
    if not job_id.isalnum():
        raise HTTPException(400, "Invalid job ID")
    meta = _read_meta(job_id)
    if not meta:
        raise HTTPException(404, "Job not found — may have expired")
    return JSONResponse({
        "job_id":          meta.get("job_id"),
        "status":          meta.get("status"),     # processing | success | failed
        "phase":           meta.get("phase", ""),  # human-readable current step
        "mode":            meta.get("mode", "auto"),
        "total_chunks":    meta.get("total_chunks",  0),
        "done_chunks":     meta.get("done_chunks",   0),
        "duration":        meta.get("duration",      0),
        "elapsed":         meta.get("elapsed",       0),
        "quality_warning": meta.get("quality_warning"),
        "error":           meta.get("error"),
        "chunks":          meta.get("chunks",        []),   # per-chunk results
        "merged":          meta.get("merged"),              # full merged result
    })

# ══════════════════════════════════════════════════════════
# FILE SERVE
# ══════════════════════════════════════════════════════════

@app.get("/api/files/{job_id}/{section}/{filename}")
def serve_chunk(job_id: str, section: str, filename: str):
    if not job_id.isalnum() or ".." in section or ".." in filename:
        raise HTTPException(400, "Invalid path")
    p = OUTPUT_DIR / job_id / section / filename
    if not p.exists():
        raise HTTPException(404, f"File not found: {p.name}")
    return FileResponse(str(p), filename=filename, media_type=_mime(filename))

@app.get("/api/merged/{job_id}/{filename}")
def serve_merged(job_id: str, filename: str):
    if not job_id.isalnum() or ".." in filename:
        raise HTTPException(400, "Invalid path")
    p = OUTPUT_DIR / job_id / "merged" / filename
    if not p.exists():
        raise HTTPException(404, f"Merged file not found: {p.name}")
    return FileResponse(str(p), filename=filename, media_type=_mime(filename))

def _mime(f: str) -> str:
    return {".mid":"audio/midi",".midi":"audio/midi",".wav":"audio/wav",
            ".mp3":"audio/mpeg",".pdf":"application/pdf",
            ".txt":"text/plain"}.get(Path(f).suffix.lower(), "application/octet-stream")
