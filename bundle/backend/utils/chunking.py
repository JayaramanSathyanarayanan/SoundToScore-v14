import logging, numpy as np, soundfile as sf
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CHUNK_SEC
log = logging.getLogger("soundtoscore")

def split_into_chunks(wav_path: str, chunk_dir: str, sr: int = 16000) -> list:
    import librosa
    y, _ = librosa.load(wav_path, sr=sr, mono=True)
    dur   = len(y) / sr
    csamp = int(CHUNK_SEC * sr)
    n_ch  = max(1, int(np.ceil(len(y) / csamp)))
    Path(chunk_dir).mkdir(parents=True, exist_ok=True)
    chunks = []
    for ci in range(n_ch):
        cy   = y[ci*csamp : min((ci+1)*csamp, len(y))]
        cst  = round(ci * CHUNK_SEC, 1)
        cen  = round(min(cst + CHUNK_SEC, dur), 1)
        path = str(Path(chunk_dir) / f"chunk_{ci+1}.wav")
        sf.write(path, cy, sr)
        del cy
        chunks.append({"index": ci+1, "path": path, "start": cst, "end": cen})
    del y
    log.info(f"Split {dur:.1f}s into {n_ch} chunks")
    return chunks
