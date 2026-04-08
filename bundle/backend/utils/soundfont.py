"""Download and validate the SoundFont file."""
import logging, shutil
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SF_FILE, SF_GITHUB_URL, SF_MIN_SIZE
log = logging.getLogger("soundtoscore")

def _valid() -> bool:
    return SF_FILE.exists() and SF_FILE.stat().st_size > SF_MIN_SIZE

def ensure_soundfont() -> str:
    if _valid():
        log.info("SoundFont already available")
        return str(SF_FILE)
    tmp = SF_FILE.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    log.warning(f"Downloading SoundFont from {SF_GITHUB_URL}")
    try:
        import requests
        with requests.get(SF_GITHUB_URL, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
        tmp.replace(SF_FILE)
        if _valid():
            log.info(f"SoundFont downloaded: {SF_FILE.stat().st_size//1024//1024}MB")
            return str(SF_FILE)
        raise RuntimeError("Downloaded file too small — invalid")
    except Exception as e:
        SF_FILE.unlink(missing_ok=True)
        raise RuntimeError(f"SoundFont download failed: {e}")
