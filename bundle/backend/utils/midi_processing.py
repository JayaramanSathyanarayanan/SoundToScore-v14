"""MIDI extraction from audio chunk using librosa YIN pitch detection."""
import numpy as np, logging
from pathlib import Path
import pretty_midi, librosa
log = logging.getLogger("soundtoscore")

def extract_midi(wav_path: str, midi_path: str, sr: int = 16000, tempo: int = 120) -> str:
    if not Path(wav_path).exists():
        raise FileNotFoundError(f"WAV not found: {wav_path}")
    y, _ = librosa.load(wav_path, sr=sr, mono=True)
    y = librosa.util.normalize(y)
    y = librosa.effects.preemphasis(y)
    f0 = librosa.yin(y, fmin=50, fmax=2000, sr=sr, frame_length=2048, hop_length=512)
    hop = 512 / sr
    times = np.arange(len(f0)) * hop
    notes_data = []
    for t, freq in zip(times, f0):
        if freq > 30 and not np.isnan(freq) and not np.isinf(freq):
            try:
                mn = int(round(librosa.hz_to_midi(freq)))
                if 21 <= mn <= 108:
                    notes_data.append((float(t), int(mn)))
            except Exception:
                continue
    pm = pretty_midi.PrettyMIDI(initial_tempo=float(tempo))
    instr = pretty_midi.Instrument(program=0)
    instr.notes = _group_notes(notes_data, hop)
    pm.instruments.append(instr)
    pm.write(midi_path)
    del y, f0
    log.info(f"MIDI extracted: {len(instr.notes)} notes -> {midi_path}")
    return midi_path

def _group_notes(notes_data, hop_size, min_dur=0.05):
    notes = []
    if not notes_data:
        return notes
    st, cp = notes_data[0]
    lt = st
    for t, pitch in notes_data[1:]:
        if pitch == cp and (t - lt) < hop_size * 4:
            lt = t
        else:
            dur = lt - st + hop_size
            if dur >= min_dur:
                notes.append(pretty_midi.Note(velocity=80, pitch=cp, start=st, end=st+dur))
            st, cp, lt = t, pitch, t
    dur = lt - st + hop_size
    if dur >= min_dur:
        notes.append(pretty_midi.Note(velocity=80, pitch=cp, start=st, end=st+dur))
    return notes
