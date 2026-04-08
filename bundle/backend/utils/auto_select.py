import logging, numpy as np
log = logging.getLogger("soundtoscore")

def select_best_stem(stems: dict, mode: str = "auto") -> str:
    if mode == "vocal":
        s = stems.get("vocals") or stems.get("other")
        log.info(f"Vocal mode -> {s}"); return s
    if mode == "instrument":
        s = stems.get("other") or stems.get("bass")
        log.info(f"Instrument mode -> {s}"); return s
    candidates = {k: v for k, v in stems.items() if k != "drums" and v}
    if not candidates:
        return list(stems.values())[0]
    scores = {}
    for name, path in candidates.items():
        try:
            scores[name] = _pitch_score(path)
            log.info(f"Stem '{name}' score: {scores[name]:.3f}")
        except Exception as e:
            log.warning(f"Score failed for '{name}': {e}"); scores[name] = 0.0
    best = max(scores, key=scores.get)
    log.info(f"Auto selected: '{best}'")
    return candidates[best]

def _pitch_score(wav_path: str) -> float:
    import librosa
    y, sr = librosa.load(wav_path, sr=16000, mono=True, duration=30.0)
    y = librosa.util.normalize(y)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"),
        sr=sr, frame_length=2048, hop_length=512)
    voiced_ratio = np.sum(voiced_flag) / max(len(voiced_flag), 1)
    mean_prob    = float(np.nanmean(voiced_probs)) if len(voiced_probs) else 0.0
    del y
    return voiced_ratio * mean_prob
