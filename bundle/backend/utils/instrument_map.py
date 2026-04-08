"""Map user instrument selection to MIDI program number."""
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import INSTRUMENT_CONFIG
log = logging.getLogger("soundtoscore")

def set_instrument_program(midi_path: str, output_path: str, instrument: str) -> str:
    import pretty_midi, shutil
    cfg = INSTRUMENT_CONFIG.get(instrument)
    if cfg is None:
        shutil.copy(midi_path, output_path)
        return output_path
    program, _ = cfg
    pm = pretty_midi.PrettyMIDI(midi_path)
    for instr in pm.instruments:
        if not instr.is_drum:
            instr.program = program
    pm.write(output_path)
    log.info(f"Set program {program} for {instrument}")
    return output_path
