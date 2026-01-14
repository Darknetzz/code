import numpy as np
import sounddevice as sd
import typer
from typing import List, Optional
import time
import json
from pathlib import Path

app = typer.Typer(
    no_args_is_help=True
)

DEFAULT_FREQUENCY = 440.0
DEFAULT_DURATION = 1.0
DEFAULT_FADE_TIME = 0.05
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_SIMPLE = False
DEFAULT_PAUSE = 0.1

DEFAULT_LOW_FREQUENCY = 20.0
DEFAULT_HIGH_FREQUENCY = 20000.0
DEFAULT_STEPS = 20

DEFAULT_AMPLITUDE = 0.5  # Safe default amplitude (0.0 to 1.0)
MAX_SAFE_AMPLITUDE = 0.7  # Maximum recommended amplitude

# ============================================================================ #
#                              FUNCTION: simple_tone                           #
# ============================================================================ #
def simple_tone(frequency: float = DEFAULT_FREQUENCY, duration: float = DEFAULT_DURATION, fs: int = DEFAULT_SAMPLE_RATE, amplitude: float = DEFAULT_AMPLITUDE):
    """Generate a simple sine wave tone.
    
    Args:
        frequency: Frequency in Hz
        duration: Duration in seconds
        fs: Sample rate in Hz
        amplitude: Amplitude (0.0 to 1.0). Default 0.5 is safe. Higher values may cause hearing damage.
    """
    # Clamp amplitude to safe range
    amplitude = max(0.0, min(amplitude, 1.0))
    
    # Generate time axis
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    # Generate a sine wave
    audio = amplitude * np.sin(2 * np.pi * frequency * t)

    return audio

# ============================================================================ #
#                            FUNCTION: generate_complex_tone                   #
# ============================================================================ #
def generate_complex_tone(fundamental, duration=DEFAULT_DURATION, fs=DEFAULT_SAMPLE_RATE):
    """Generate a complex tone with harmonics."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    
    # We create a 'recipe' for the sound (Harmonic number, Amplitude)
    # Fundamental, Octave, Octave + Fifth, etc.
    harmonics = [
        (1, 0.5),   # Fundamental
        (2, 0.2),   # 1st Overtone
        (3, 0.1),   # 2nd Overtone
        (4, 0.05)   # 3rd Overtone
    ]
    
    # Sum the sine waves
    audio = sum(amp * np.sin(2 * np.pi * fundamental * h * t) for h, amp in harmonics)
    
    # Apply a quick 'Envelope' to prevent clicking at start/end
    fade = int(fs * DEFAULT_FADE_TIME * 2)  # Use 2x fade time for complex tone envelope
    envelope = np.ones_like(audio)
    envelope[:fade] = np.linspace(0, 1, fade) # Fade in
    envelope[-fade:] = np.linspace(1, 0, fade) # Fade out
    
    return audio * envelope

# ============================================================================ #
#                              FUNCTION: play_tone                             #
# ============================================================================ #
def play_tone(tone, fs: int = DEFAULT_SAMPLE_RATE):
    """Play a tone using sounddevice."""
    sd.play(tone, fs)
    sd.wait()

# ============================================================================ #
#                              FUNCTION: play_freq                             #
# ============================================================================ #
def play_freq(
    frequency,
    duration = DEFAULT_DURATION,  # Can be float or List[float]
    pause: float = DEFAULT_PAUSE,
    simple: bool = DEFAULT_SIMPLE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    show_output: bool = True,
    output_prefix: str = "  "
):
    """Generate and play tone(s) at the specified frequency/frequencies.
    
    Args:
        frequency: Frequency in Hz (float) or list of frequencies (List[float])
        duration: Duration per tone in seconds (float) or list of durations (List[float])
        pause: Pause between tones in seconds (default: DEFAULT_PAUSE, ignored for single frequency)
        simple: Use simple sine wave (True) or complex tone (False)
        sample_rate: Sample rate in Hz
        show_output: Whether to display output message (default: True)
        output_prefix: Prefix for output message (default: "  ")
    """
    # Handle single frequency or list
    if isinstance(frequency, (int, float)):
        frequencies = [frequency]
        single_freq = True
    else:
        frequencies = frequency
        single_freq = False
    
    # Early return if no frequencies
    if not frequencies:
        return
    
    # Handle single duration or list
    if isinstance(duration, (int, float)):
        durations = [duration] * len(frequencies)
    elif isinstance(duration, list):
        durations = duration
        if len(durations) != len(frequencies):
            raise ValueError(f"Number of durations ({len(durations)}) must match number of frequencies ({len(frequencies)})")
    else:
        raise TypeError(f"duration must be a number or list, got {type(duration).__name__}")
    
    for i, freq in enumerate(frequencies, 1):
        current_duration = durations[i - 1]
        # Use pause only if not the last tone and not a single frequency
        current_pause = pause if (not single_freq and i < len(frequencies)) else 0.0
        
        # Format output with index for multiple frequencies
        if show_output:
            if single_freq:
                prefix = output_prefix
            else:
                prefix = f"{output_prefix}[{i}/{len(frequencies)}] "
            typer.echo(f"{prefix}Playing {freq} Hz for {current_duration}s...")
        
        if simple:
            tone = simple_tone(freq, current_duration, sample_rate)
        else:
            tone = generate_complex_tone(freq, current_duration, sample_rate)
        
        play_tone(tone, sample_rate)
        
        if current_pause > 0:
            time.sleep(current_pause)

# ============================================================================ #
#                         FUNCTION: generate_sequence_with_fade                #
# ============================================================================ #
def generate_sequence_with_fade(
    frequencies: List[float],
    duration: float = DEFAULT_DURATION,
    pause: float = DEFAULT_PAUSE,
    fade_time: float = DEFAULT_FADE_TIME,
    simple: bool = DEFAULT_SIMPLE,
    fs: int = DEFAULT_SAMPLE_RATE
) -> np.ndarray:
    """Generate a sequence of tones with smooth crossfade transitions.
    
    Args:
        frequencies: List of frequencies to play
        duration: Duration of each tone in seconds
        pause: Pause between tones in seconds (can be negative for overlap)
        fade_time: Time for fade-in/fade-out in seconds
        simple: Use simple sine wave (True) or complex tone (False)
        fs: Sample rate in Hz
    
    Returns:
        Combined audio array with smooth transitions
    """
    if not frequencies:
        return np.array([])
    
    # Generate individual tones
    tones = []
    for freq in frequencies:
        if simple:
            tone = simple_tone(freq, duration, fs)
        else:
            tone = generate_complex_tone(freq, duration, fs)
        tones.append(tone)
    
    # Calculate fade samples
    fade_samples = int(fs * fade_time)
    
    # Apply fade-in to first tone and fade-out to last tone
    if len(tones) > 0:
        # Fade in first tone
        if fade_samples > 0 and len(tones[0]) > fade_samples:
            fade_in = np.linspace(0, 1, fade_samples)
            tones[0][:fade_samples] *= fade_in
        
        # Fade out last tone
        if fade_samples > 0 and len(tones[-1]) > fade_samples:
            fade_out = np.linspace(1, 0, fade_samples)
            tones[-1][-fade_samples:] *= fade_out
    
    # Combine tones with crossfade
    if len(tones) == 1:
        return tones[0]
    
    # Calculate pause samples (can be negative for overlap)
    pause_samples = int(fs * pause)
    
    # Calculate total length
    tone_length = len(tones[0])
    total_length = tone_length + (len(tones) - 1) * (tone_length + pause_samples)
    
    # Create output array
    output = np.zeros(total_length)
    
    # Place tones with crossfade
    for i, tone in enumerate(tones):
        start_idx = i * (tone_length + pause_samples)
        end_idx = start_idx + len(tone)
        
        if i > 0 and pause_samples < 0:
            # Overlap: crossfade with previous tone
            overlap = abs(pause_samples)
            if overlap < fade_samples:
                # Short overlap: simple crossfade
                fade_out = np.linspace(1, 0, overlap)
                fade_in = np.linspace(0, 1, overlap)
                
                # Fade out previous tone's end
                prev_end = start_idx
                prev_start = prev_end - overlap
                if prev_start >= 0:
                    output[prev_start:prev_end] *= fade_out
                
                # Fade in current tone's start
                output[start_idx:start_idx + overlap] += tone[:overlap] * fade_in
                output[start_idx + overlap:end_idx] += tone[overlap:]
            else:
                # Longer overlap: full crossfade
                fade_out = np.linspace(1, 0, fade_samples)
                fade_in = np.linspace(0, 1, fade_samples)
                
                # Fade out previous tone
                prev_end = start_idx
                prev_start = prev_end - fade_samples
                if prev_start >= 0:
                    output[prev_start:prev_end] *= fade_out
                
                # Fade in current tone
                output[start_idx:start_idx + fade_samples] += tone[:fade_samples] * fade_in
                output[start_idx + fade_samples:end_idx] += tone[fade_samples:]
        else:
            # No overlap or pause: just add the tone
            if i > 0:
                # Fade in at the start
                if fade_samples > 0:
                    fade_in = np.linspace(0, 1, fade_samples)
                    output[start_idx:start_idx + fade_samples] += tone[:fade_samples] * fade_in
                    output[start_idx + fade_samples:end_idx] += tone[fade_samples:]
                else:
                    output[start_idx:end_idx] += tone
            else:
                output[start_idx:end_idx] = tone
    
    return output

# ============================================================================ #
#                              CLI COMMANDS                                    #
# ============================================================================ #


# ────────────────────────────── COMMAND: single ───────────────────────────── #
@app.command()
def single(
    frequency: float = typer.Argument(DEFAULT_FREQUENCY, help="Frequency in Hz (e.g., 440 for A4)"),
    duration: float = typer.Option(DEFAULT_DURATION, "--duration", "-d", help="Duration in seconds"),
    simple: bool = typer.Option(DEFAULT_SIMPLE, "--simple", "-s", help="Use simple sine wave instead of complex tone"),
    sample_rate: int = typer.Option(DEFAULT_SAMPLE_RATE, "--sample-rate", "-r", help="Sample rate in Hz")
):
    """Play a single tone at the specified frequency."""
    typer.echo(f"Playing {'simple' if simple else 'complex'} tone at {frequency} Hz for {duration} seconds...")
    
    if simple:
        tone = simple_tone(frequency, duration, sample_rate)
    else:
        tone = generate_complex_tone(frequency, duration, sample_rate)
    
    play_tone(tone, sample_rate)
    typer.echo("Done!")

# ────────────────────────────── COMMAND: sequence ──────────────────────────── #
@app.command()
def sequence(
    frequencies: List[float] = typer.Argument(..., help="Frequencies in Hz (space-separated, e.g., 440 523.25 659.25)"),
    duration: float = typer.Option(DEFAULT_DURATION, "--duration", "-d", help="Duration per tone in seconds"),
    pause: float = typer.Option(DEFAULT_PAUSE, "--pause", "-p", help="Pause between tones in seconds (negative for overlap/crossfade)"),
    simple: bool = typer.Option(DEFAULT_SIMPLE, "--simple", "-s", help="Use simple sine wave instead of complex tone"),
    sample_rate: int = typer.Option(DEFAULT_SAMPLE_RATE, "--sample-rate", "-r", help="Sample rate in Hz"),
    fade: bool = typer.Option(True, "--fade/--no-fade", help="Use smooth crossfade transitions between tones (default: True)")
):
    """Play a sequence of tones."""
    typer.echo(f"Playing sequence of {len(frequencies)} tones: {frequencies}")
    typer.echo(f"Crossfade: {'enabled' if fade else 'disabled'}")
    typer.echo("")
    
    if fade:
        # Use smooth crossfade transitions
        typer.echo(f"Generating sequence with smooth crossfade transitions ({len(frequencies)} tones)...")
        combined_audio = generate_sequence_with_fade(
            frequencies, duration, pause, DEFAULT_FADE_TIME, simple, sample_rate
        )
        typer.echo("Playing combined sequence...")
        play_tone(combined_audio, sample_rate)
    else:
        # Use sequential playback with pauses
        typer.echo("Using sequential playback (no crossfade)...")
        play_freq(frequencies, duration, pause, simple, sample_rate, 
                  show_output=True, output_prefix="  ")
    
    typer.echo("Sequence complete!")

# ────────────────────────────── COMMAND: hearing_test ─────────────────────── #
@app.command()
def hearing_test(
    duration: float = typer.Option(1.5, "--duration", "-d", help="Duration per tone in seconds"),
    pause: float = typer.Option(1.0, "--pause", "-p", help="Pause between tones in seconds"),
    sample_rate: int = typer.Option(DEFAULT_SAMPLE_RATE, "--sample-rate", "-r", help="Sample rate in Hz"),
    low_freq: float = typer.Option(DEFAULT_LOW_FREQUENCY, "--low", help="Lowest frequency to test (Hz)"),
    high_freq: float = typer.Option(DEFAULT_HIGH_FREQUENCY, "--high", help="Highest frequency to test (Hz)"),
    steps: int = typer.Option(DEFAULT_STEPS, "--steps", help="Number of frequency steps in the test")
):
    """
    Perform a hearing test by playing tones across the human hearing range.
    
    The test plays tones from low to high frequencies. Note which frequencies
    you can and cannot hear to determine your hearing range.
    
    Typical human hearing: 20 Hz - 20,000 Hz
    
    ⚠️  SAFETY WARNING: 
    - Even inaudible frequencies can cause hearing damage at high volumes
    - Stop immediately if you experience discomfort, pain, or ringing
    - Do not use headphones at maximum volume
    - This is for educational purposes only, not medical diagnosis
    """
    typer.echo("=" * 60)
    typer.echo("HEARING TEST")
    typer.echo("=" * 60)
    typer.echo("⚠️  SAFETY WARNING ⚠️")
    typer.echo("Even frequencies you cannot hear can damage your hearing at high volumes!")
    typer.echo("Stop immediately if you experience any discomfort, pain, or ringing.")
    typer.echo("Do not use headphones at maximum volume.")
    typer.echo("=" * 60)
    typer.echo(f"Testing frequency range: {low_freq} Hz to {high_freq} Hz")
    typer.echo(f"Number of steps: {steps}")
    typer.echo(f"Duration per tone: {duration} seconds")
    typer.echo(f"Pause between tones: {pause} seconds")
    typer.echo("")
    typer.echo("Note: Use simple sine waves for accurate frequency testing")
    typer.echo("Listen carefully and note which frequencies you can hear.")
    typer.echo("")
    
    # Generate frequency steps (logarithmic scale is more natural for hearing)
    frequencies = np.logspace(np.log10(low_freq), np.log10(high_freq), steps)
    
    typer.echo("Starting test in 3 seconds...")
    time.sleep(1)
    typer.echo("2...")
    time.sleep(1)
    typer.echo("1...")
    time.sleep(1)
    typer.echo("")
    
    # Round frequencies for display
    frequencies_rounded = [round(f, 2) for f in frequencies]
    
    audible_count = 0
    for i, freq in enumerate(frequencies_rounded, 1):
        # Use simple tone for accurate frequency representation
        current_pause = pause if i < len(frequencies_rounded) else 0.0
        play_freq(freq, duration, current_pause, simple=True, sample_rate=sample_rate,
                  show_output=True, output_prefix=f"[{i}/{steps}] ")
        
        typer.echo(" ✓")
        audible_count += 1
    
    typer.echo("")
    typer.echo("=" * 60)
    typer.echo("TEST COMPLETE")
    typer.echo("=" * 60)
    typer.echo(f"Tested {steps} frequencies from {low_freq} Hz to {high_freq} Hz")
    typer.echo("")
    typer.echo("Note: This is a basic test. For professional hearing assessment,")
    typer.echo("      consult an audiologist.")
    typer.echo("")
    typer.echo("⚠️  If you experienced any discomfort, pain, or ringing, stop using")
    typer.echo("   this tool and consult a medical professional if symptoms persist.")

# ============================================================================ #
#                            FUNCTION: load_and_play_json                      #
# ============================================================================ #
def load_and_play_json(file_path: str, sample_rate: Optional[int] = None, use_fade: bool = True):
    """Load a JSON file and play the sequence defined in it.
    
    Supports two JSON formats:
    1. Simple format: {"notes": [freq1, freq2, ...], "duration": 0.5, "pause": 0.1, ...}
    2. Detailed format: {"notes": [{"frequency": 440, "duration": 1.0, "pause": 0.1}, ...]}
    
    Args:
        file_path: Path to JSON file
        sample_rate: Optional sample rate override
        use_fade: Whether to use smooth crossfade transitions (only works with simple format)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Get metadata
    name = data.get("name", file_path.stem)
    description = data.get("description", "")
    # Command line sample_rate overrides file setting
    file_sample_rate = sample_rate if sample_rate is not None else data.get("sample_rate", DEFAULT_SAMPLE_RATE)
    file_simple = data.get("simple", DEFAULT_SIMPLE)
    default_duration = data.get("duration", DEFAULT_DURATION)
    default_pause = data.get("pause", DEFAULT_PAUSE)
    # Check if fade is requested in JSON file
    file_fade = data.get("fade", use_fade)
    
    typer.echo(f"Playing: {name}")
    if description:
        typer.echo(f"Description: {description}")
    
    # Show fade status
    fade_status = "enabled" if file_fade else "disabled"
    typer.echo(f"Crossfade: {fade_status}")
    typer.echo("")
    
    notes = data.get("notes", [])
    if not notes:
        raise ValueError("No 'notes' field found in JSON file")
    
    # Check if it's simple format (list of frequencies) or detailed format (list of objects)
    if isinstance(notes[0], (int, float)):
        # Simple format: list of frequencies
        frequencies = notes
        if file_fade:
            # Use smooth crossfade transitions
            typer.echo(f"Generating sequence with smooth crossfade transitions ({len(frequencies)} tones)...")
            combined_audio = generate_sequence_with_fade(
                frequencies, default_duration, default_pause, DEFAULT_FADE_TIME, 
                file_simple, file_sample_rate
            )
            typer.echo("Playing combined sequence...")
            play_tone(combined_audio, file_sample_rate)
        else:
            # Use sequential playback
            typer.echo("Using sequential playback (no crossfade)...")
            play_freq(frequencies, default_duration, default_pause, file_simple, file_sample_rate,
                      show_output=True, output_prefix="  ")
    else:
        # Detailed format: list of note objects - need individual handling for per-note settings
        # Crossfade not supported for detailed format due to per-note variations
        for i, note in enumerate(notes, 1):
            freq = note.get("frequency")
            if freq is None:
                raise ValueError(f"Note {i} missing 'frequency' field")
            
            note_duration = note.get("duration", default_duration)
            note_pause = note.get("pause", default_pause)
            note_simple = note.get("simple", file_simple)
            
            # Use pause only if not the last note
            current_pause = note_pause if i < len(notes) else 0.0
            play_freq(freq, note_duration, current_pause, note_simple, file_sample_rate,
                     show_output=True, output_prefix=f"  [{i}/{len(notes)}] ")
    
    typer.echo("")
    typer.echo("Playback complete!")

# ────────────────────────────── COMMAND: play_file ─────────────────────────── #
@app.command()
def play_file(
    file_path: str = typer.Argument(..., help="Path to JSON file containing tone sequence"),
    sample_rate: Optional[int] = typer.Option(None, "--sample-rate", "-r", help="Sample rate in Hz (overrides file setting if provided)"),
    fade: bool = typer.Option(True, "--fade/--no-fade", help="Use smooth crossfade transitions (default: True, only for simple format)")
):
    """
    Play a sequence of tones from a JSON file.
    
    JSON Format Examples:
    
    Simple format:
    {
      "name": "C Major Scale",
      "notes": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25],
      "duration": 0.5,
      "pause": 0.1,
      "simple": false
    }
    
    Detailed format:
    {
      "name": "Custom Song",
      "notes": [
        {"frequency": 440.0, "duration": 1.0, "pause": 0.2},
        {"frequency": 523.25, "duration": 0.5, "pause": 0.1}
      ]
    }
    """
    try:
        load_and_play_json(file_path, sample_rate, fade)
    except FileNotFoundError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        typer.echo(f"❌ Error parsing JSON file: {e}", err=True)
        raise typer.Exit(1)


# ============================================================================ #
#                                   FUNCTION                                   #
# ============================================================================ #
if __name__ == "__main__":
    app()