"""
services/orchestrator.py — SoundToScore V14
Full-band orchestration: synthesize 5 brass band layers and mix.
Files saved to: job_dir/orchestra/{filename}
Served at:      /api/orch/{job_id}/{filename}
"""
import logging, subprocess, shutil
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ORCHESTRA_LAYERS, INSTRUMENT_CONFIG
from utils.transpose      import transpose_midi
from utils.instrument_map import set_instrument_program
from utils.synth          import synthesize
from utils.effects        import apply_effects

log = logging.getLogger("soundtoscore")


def orchestrate(midi_path: str, job_dir: str, sf2: str) -> dict:
    """
    Create a 5-layer brass band arrangement from a single MIDI file.
    Saves all files to: job_dir/orchestra/
    Returns {layer_name: absolute_file_path}
    """
    orch_dir = Path(job_dir) / "orchestra"
    orch_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for layer in ORCHESTRA_LAYERS:
        name       = layer["name"]
        instrument = layer["instrument"]
        program, semitones = INSTRUMENT_CONFIG.get(instrument, (0, 0))

        try:
            safe_name = name.lower().replace(" ", "_")

            # Transpose
            t_midi = str(orch_dir / f"{safe_name}_t.mid")
            transpose_midi(midi_path, t_midi, semitones=semitones)

            # Set program
            m_midi = str(orch_dir / f"{safe_name}_m.mid")
            set_instrument_program(t_midi, m_midi, instrument)

            # Synthesize
            dry = str(orch_dir / f"{safe_name}_dry.wav")
            synthesize(m_midi, dry, sf2)

            # Effects
            wet = str(orch_dir / f"{safe_name}.wav")
            apply_effects(dry, wet)

            results[name] = wet
            log.info(f"Orchestra '{name}' -> {wet}")

        except Exception as e:
            log.warning(f"Orchestra layer '{name}' failed: {e}")

    # Mix all layers into full_mix.wav
    if len(results) > 0:
        mix_path = str(orch_dir / "full_mix.wav")
        _mix_layers(list(results.values()), mix_path)
        results["Full Mix"] = mix_path

    return results   # {layer_name: absolute_path}


def _mix_layers(wav_files: list, output: str):
    """Mix multiple WAV files using FFmpeg amix."""
    valid = [f for f in wav_files if Path(f).exists()]
    if not valid:
        return
    if len(valid) == 1:
        shutil.copy(valid[0], output)
        return
    inputs = []
    for f in valid:
        inputs += ["-i", f]
    cmd = (["ffmpeg", "-y"] + inputs +
           ["-filter_complex",
            f"amix=inputs={len(valid)}:duration=longest:normalize=1",
            output])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        shutil.copy(valid[0], output)
        log.warning("Mix failed — using first layer only")
    else:
        log.info(f"Mixed {len(valid)} layers -> {output}")
