"""Synthesize MIDI to audio using FluidSynth + SoundFont."""
import subprocess, logging, shutil
from pathlib import Path
log = logging.getLogger("soundtoscore")

def synthesize(midi_path: str, output_wav: str, sf2_path: str) -> str:
    if not Path(midi_path).exists():
        raise FileNotFoundError(f"MIDI not found: {midi_path}")
    if not Path(sf2_path).exists():
        raise FileNotFoundError(f"SoundFont not found: {sf2_path}")
    if not shutil.which("fluidsynth"):
        raise RuntimeError("fluidsynth not installed")
    cmd = ["fluidsynth", "-ni", "-g", "1.4", "-r", "44100",
           "-F", output_wav, sf2_path, midi_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"FluidSynth: {r.stderr[-400:]}")
    if not Path(output_wav).exists():
        raise FileNotFoundError("FluidSynth produced no output")
    log.info(f"Synthesized -> {output_wav}")
    return output_wav
