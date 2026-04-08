import subprocess, logging, shutil
from pathlib import Path
log = logging.getLogger("soundtoscore")

def separate_stems(input_path: str, output_dir: str) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        import demucs
        has_demucs = True
    except ImportError:
        has_demucs = False
    if not has_demucs:
        log.warning("Demucs not installed — using original audio for all stems")
        fallback = str(output_dir / "other.wav")
        shutil.copy(input_path, fallback)
        return {"other": fallback, "vocals": fallback, "bass": fallback, "drums": fallback}
    try:
        cmd = ["python3", "-m", "demucs", "--two-stems", "vocals",
               "-n", "htdemucs", "--out", str(output_dir), input_path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"Demucs: {r.stderr[-400:]}")
        stems = {}
        for stem in ["vocals", "drums", "bass", "other"]:
            found = list(output_dir.rglob(f"{stem}.wav"))
            if found:
                stems[stem] = str(found[0])
        if not stems:
            raise RuntimeError("Demucs produced no output")
        log.info(f"Stems: {list(stems.keys())}")
        return stems
    except Exception as e:
        log.warning(f"Demucs failed ({e}) — fallback to original")
        fallback = str(output_dir / "other.wav")
        shutil.copy(input_path, fallback)
        return {"other": fallback, "vocals": fallback, "bass": fallback, "drums": fallback}
