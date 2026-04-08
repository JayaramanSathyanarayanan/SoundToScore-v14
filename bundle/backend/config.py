"""config.py — SoundToScore V14 central configuration"""
from pathlib import Path

BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads";              UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = BASE_DIR / "outputs";              OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR   = BASE_DIR / "temp";                 TEMP_DIR.mkdir(exist_ok=True)
SF_DIR     = BASE_DIR / "assets" / "soundfonts"; SF_DIR.mkdir(parents=True, exist_ok=True)

SF_FILE       = SF_DIR / "GeneralUser_GS.sf2"
SF_GITHUB_URL = "https://github.com/JayaramanSathyanarayanan/SoundToScore/releases/download/v1.0/GeneralUser_GS.sf2"
SF_MIN_SIZE   = 5 * 1024 * 1024

CHUNK_SEC           = 20
SAMPLE_RATE         = 16000
MAX_BYTES           = 100 * 1024 * 1024
MAX_CONCURRENT_JOBS = 2
JOB_TTL             = 7200
MIN_NOTE_DURATION   = 0.08
MIN_VELOCITY        = 45
QUANTIZE_GRID       = 0.0625

# (midi_program, semitone_shift)
# Brass band: Bb instrument = +2, Eb = +9, C = 0
INSTRUMENT_CONFIG = {
    # ── Brass Band ─────────────────────────────────────────
    "soprano_cornet":   (56, +9),
    "solo_cornet":      (56, +2),
    "repiano_cornet":   (56, +2),
    "cornet_2nd":       (56, +2),
    "cornet_3rd":       (56, +2),
    "flugelhorn":       (56, +2),
    "solo_tenor_horn":  (60, +9),
    "tenor_horn_1st":   (60, +9),
    "tenor_horn_2nd":   (60, +9),
    "baritone_1st":     (58, +2),
    "baritone_2nd":     (58, +2),
    "euphonium":        (58, +2),
    "trombone_1st":     (57, +2),
    "trombone_2nd":     (57, +2),
    "bass_trombone":    (57,  0),
    "eb_bass":          (43, +9),
    "bbb_bass":         (43, +2),
    # ── Trumpet family ─────────────────────────────────────
    "trumpet_bb":       (56, +2),
    "trumpet_c":        (56,  0),
    "trumpet_d":        (56, -2),
    "trumpet_eb":       (56, -9),
    "piccolo_trumpet":  (56, -12),
    "pocket_trumpet":   (56, +2),
    "muted_trumpet":    (59, +2),
    "harmon_trumpet":   (59, +2),
    # ── French Horn & Others ───────────────────────────────
    "french_horn":      (60, +7),
    "tenor_horn":       (60, +9),
    "baritone":         (58, +2),
    "tuba":             (58,  0),
    # ── Woodwinds ──────────────────────────────────────────
    "flute":            (73,  0),
    "piccolo":          (72,  0),
    "alto_flute":       (73,  0),
    "clarinet":         (71, +2),
    "bass_clarinet":    (71, +14),
    "oboe":             (68,  0),
    "bassoon":          (70,  0),
    "alto_sax":         (65, +9),
    "tenor_sax":        (66, +2),
    "baritone_sax":     (67, +9),
    # ── Piano ──────────────────────────────────────────────
    "concert_grand":    ( 0,  0),
    "baby_grand":       ( 0,  0),
    "upright":          ( 1,  0),
    "studio_piano":     ( 2,  0),
    "honky_tonk":       ( 3,  0),
    "rhodes":           ( 4,  0),
    "wurlitzer":        ( 4,  0),
    "fm_piano":         ( 5,  0),
    "felt_piano":       ( 0,  0),
    "prepared_piano":   ( 0,  0),
    # ── Strings ────────────────────────────────────────────
    "violin":           (40,  0),
    "viola":            (41,  0),
    "cello":            (42,  0),
    "double_bass":      (43,  0),
    "string_ensemble":  (48,  0),
    "pizzicato":        (45,  0),
    "tremolo":          (44,  0),
    "staccato":         (48,  0),
    # ── Guitar ─────────────────────────────────────────────
    "acoustic_guitar":  (24,  0),
    "electric_guitar":  (27,  0),
    "distortion_guitar":(30,  0),
    "electric_bass":    (33,  0),
    "slap_bass":        (36,  0),
    # ── Percussion ─────────────────────────────────────────
    "timpani":          (47,  0),
    "glockenspiel":     ( 9,  0),
    "xylophone":        (13,  0),
    "tubular_bells":    (14,  0),
    "drum_kit":         ( 0,  0),
    "snare_drum":       ( 0,  0),
    "bass_drum":        ( 0,  0),
    "cymbals":          ( 0,  0),
    "triangle":         ( 0,  0),
    "tambourine":       ( 0,  0),
    # ── Synth ──────────────────────────────────────────────
    "synth_lead":       (80,  0),
    "synth_pad":        (88,  0),
    "synth_bass":       (38,  0),
    # ── World ──────────────────────────────────────────────
    "sitar":            (104, 0),
    "tabla":            (115, 0),
    "pan_flute":        (75,  0),
    "accordion":        (21,  0),
}

VALID_INSTRUMENTS = set(INSTRUMENT_CONFIG.keys())

# Full-band orchestration layers (V14)
ORCHESTRA_LAYERS = [
    {"name": "Melody",      "instrument": "solo_cornet",   "role": "melody"},
    {"name": "Harmony",     "instrument": "tenor_horn",    "role": "harmony"},
    {"name": "Low Harmony", "instrument": "euphonium",     "role": "low_harmony"},
    {"name": "Bass",        "instrument": "eb_bass",       "role": "bass"},
    {"name": "Support",     "instrument": "trombone_1st",  "role": "support"},
]
