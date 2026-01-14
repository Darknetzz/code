# pysound

A Python library and CLI tool for generating and playing audio tones using NumPy and sounddevice.

## Features

- Generate simple sine wave tones
- Generate complex tones with harmonics
- Play single tones or sequences of tones
- Command-line interface using Typer
- Configurable frequency, duration, and sample rate

## ⚠️ Safety Warning

**IMPORTANT: Hearing Safety Information**

This tool can potentially cause hearing damage if used improperly. Please read and understand the following:

### Risks

1. **Inaudible Frequencies Can Still Cause Damage**
   - Even if you cannot consciously hear a frequency (especially above 20 kHz), it can still damage your hearing at high volumes
   - Your ears may respond to ultrasonic frequencies even if your brain doesn't register them as sound
   - Damage can occur without immediate pain or discomfort

2. **High Volume Risks**
   - Very loud sounds (>85 dB) can cause permanent hearing damage
   - Damage can occur even from short exposures
   - Once hearing is damaged, it often cannot be fully restored

3. **Low Frequency Risks**
   - Very low frequencies (<20 Hz) can cause physical discomfort, nausea, or dizziness
   - These frequencies are felt more than heard and can be harmful at high volumes

4. **High Frequency Risks**
   - Frequencies above 20 kHz (ultrasonic) can cause damage even if inaudible
   - Young people may hear up to 20 kHz, but older adults typically hear less
   - Damage from ultrasonic frequencies may not be immediately noticeable

### Safety Guidelines

- ✅ **DO**: Use at moderate volume levels
- ✅ **DO**: Stop immediately if you experience any discomfort, pain, or ringing (tinnitus)
- ✅ **DO**: Take breaks between tests
- ✅ **DO**: Use speakers rather than headphones when possible
- ❌ **DON'T**: Use headphones at maximum volume
- ❌ **DON'T**: Test frequencies above 20 kHz for extended periods
- ❌ **DON'T**: Ignore signs of discomfort or pain
- ❌ **DON'T**: Use this tool if you have existing hearing conditions without consulting a doctor

### What Happens with Inaudible Frequencies at High Volume?

If you listen to an inaudible frequency (e.g., 25 kHz) at very loud volume:

1. **Physical Damage**: The sound waves can still physically damage the hair cells in your inner ear
2. **No Warning**: Since you can't hear it, you may not realize damage is occurring
3. **Delayed Symptoms**: You might not notice hearing loss until later
4. **Permanent Damage**: Once hair cells are damaged, they typically don't regenerate

**Bottom Line**: If you can't hear it, that doesn't mean it can't hurt you. Always use this tool at safe, moderate volume levels.

**This tool is for educational purposes only. For professional hearing assessment, consult an audiologist.**

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install numpy sounddevice typer[all]
```

## Usage

### Command Line Interface

The tool provides two main commands: `single` for playing a single tone, and `sequence` for playing multiple tones in sequence.

#### Play a Single Tone

```bash
# Play default A4 (440 Hz) tone
python pysound.py single

# Play a specific frequency
python pysound.py single 523.25

# Play with custom duration
python pysound.py single 440 --duration 3.0

# Play a simple sine wave (instead of complex tone)
python pysound.py single 440 --simple

# Play with custom sample rate
python pysound.py single 440 --sample-rate 48000

# Combine options
python pysound.py single 523.25 -d 2.5 -s -r 44100
```

#### Play a Sequence of Tones

```bash
# Play a sequence of frequencies (C major chord) with smooth crossfades (default)
python pysound.py sequence 261.63 329.63 392.00

# Play sequence with custom duration per tone
python pysound.py sequence 440 523.25 659.25 --duration 0.5

# Play sequence with pause between tones (negative pause creates overlap for crossfade)
python pysound.py sequence 440 523.25 659.25 --pause -0.05

# Disable crossfade for sequential playback with pauses
python pysound.py sequence 440 523.25 659.25 --no-fade --pause 0.2

# Play simple tones in sequence
python pysound.py sequence 440 523.25 659.25 --simple

# Full example with all options
python pysound.py sequence 261.63 329.63 392.00 -d 1.0 -p 0.15 -s
```

**Note**: By default, sequences use smooth crossfade transitions between tones. Use `--no-fade` to disable crossfades and use sequential playback with pauses instead.

#### Hearing Test

Test your hearing range by playing tones across the frequency spectrum:

```bash
# Basic hearing test (20 Hz to 20,000 Hz, 20 steps)
python pysound.py hearing-test

# Custom frequency range
python pysound.py hearing-test --low 50 --high 15000

# More detailed test with more steps
python pysound.py hearing-test --steps 30

# Shorter tones with longer pauses
python pysound.py hearing-test --duration 1.0 --pause 2.0
```

The hearing test plays tones from low to high frequencies using a logarithmic scale (which matches how humans perceive pitch). Listen carefully and note which frequencies you can hear to determine your hearing range.

**⚠️ CRITICAL SAFETY WARNING**: 
- **Even inaudible frequencies can damage your hearing at high volumes**
- **Stop immediately if you experience any discomfort, pain, or ringing**
- **Do not use headphones at maximum volume**
- **This is a basic test for educational purposes only**
- **For professional hearing assessment, consult an audiologist**

#### Play from JSON File

Play a sequence of tones from a JSON file:

```bash
# Play a sample file with smooth crossfades (default)
python pysound.py play-file samples/music/c_major_scale.json

# Play with custom sample rate
python pysound.py play-file samples/music/twinkle_twinkle.json --sample-rate 48000

# Disable crossfade for sequential playback
python pysound.py play-file samples/music/c_major_scale.json --no-fade
```

**JSON Format Examples:**

Simple format (list of frequencies):
```json
{
  "name": "C Major Scale",
  "notes": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25],
  "duration": 0.5,
  "pause": -0.05,
  "fade": true,
  "simple": false
}
```

**Note**: 
- `"fade": true` enables smooth crossfade transitions (default: true)
- Negative `pause` values create overlap for better crossfading
- Crossfade only works with simple format (list of frequencies)

Detailed format (individual note settings):
```json
{
  "name": "Custom Song",
  "notes": [
    {"frequency": 440.0, "duration": 1.0, "pause": 0.2},
    {"frequency": 523.25, "duration": 0.5, "pause": 0.1}
  ],
  "simple": false
}
```

**Note**: Crossfade is not supported for detailed format due to per-note variations in duration and pause settings.

**Pre-made Samples:**

Check out the `samples/music/` folder for pre-made musical sequences:
- C Major Scale
- C Major Chord
- Twinkle Twinkle Little Star
- Happy Birthday
- Pentatonic Scale
- Chord Progressions
- And more!

See `samples/music/README.md` for details.

#### Get Help

```bash
# General help
python pysound.py --help

# Help for specific command
python pysound.py single --help
python pysound.py sequence --help
python pysound.py hearing-test --help
python pysound.py play-file --help
```

### Command Options

#### `single` command:
- `frequency` (positional argument): Frequency in Hz (default: 440.0)
- `--duration, -d`: Duration in seconds (default: 1.0)
- `--simple, -s`: Use simple sine wave instead of complex tone (default: False)
- `--sample-rate, -r`: Sample rate in Hz (default: 44100)

#### `sequence` command:
- `frequencies` (positional arguments): Space-separated frequencies in Hz (required)
- `--duration, -d`: Duration per tone in seconds (default: 1.0)
- `--pause, -p`: Pause between tones in seconds (default: 0.1, negative for overlap/crossfade)
- `--simple, -s`: Use simple sine wave instead of complex tone (default: False)
- `--sample-rate, -r`: Sample rate in Hz (default: 44100)
- `--fade/--no-fade`: Use smooth crossfade transitions between tones (default: True)

#### `hearing-test` command:
- `--duration, -d`: Duration per tone in seconds (default: 1.5)
- `--pause, -p`: Pause between tones in seconds (default: 1.0)
- `--sample-rate, -r`: Sample rate in Hz (default: 44100)
- `--low`: Lowest frequency to test in Hz (default: 20.0)
- `--high`: Highest frequency to test in Hz (default: 20000.0)
- `--steps`: Number of frequency steps in the test (default: 20)

#### `play-file` command:
- `file_path` (positional argument): Path to JSON file containing tone sequence (required)
- `--sample-rate, -r`: Sample rate in Hz (default: 44100, overrides file setting)
- `--fade/--no-fade`: Use smooth crossfade transitions (default: True, only for simple format)

### Human Hearing Range

The typical human hearing range is approximately **20 Hz to 20,000 Hz (20 kHz)**:
- **Lower limit**: ~20 Hz (very low bass, felt more than heard)
- **Upper limit**: ~20,000 Hz (varies by age; young adults can hear up to ~20 kHz, but this decreases with age)
- **Most sensitive range**: ~2,000–5,000 Hz (optimal for speech perception)

**Note**: While the tool can generate frequencies outside this range, they may not be audible to most people.

### Common Musical Frequencies

Here are some common note frequencies for reference:

| Note | Frequency (Hz) |
|------|----------------|
| C4   | 261.63         |
| D4   | 293.66         |
| E4   | 329.63         |
| F4   | 349.23         |
| G4   | 392.00         |
| A4   | 440.00         |
| B4   | 493.88         |
| C5   | 523.25         |

## Programmatic Usage

You can also import and use the functions in your own Python code:

```python
from pysound import simple_tone, generate_complex_tone, play_tone

# Generate and play a simple tone
tone = simple_tone(frequency=440.0, duration=2.0, fs=44100)
play_tone(tone, fs=44100)

# Generate and play a complex tone with harmonics
tone = generate_complex_tone(fundamental=440.0, duration=2.0, fs=44100)
play_tone(tone, fs=44100)
```

## Technical Details

- **Simple Tone**: Pure sine wave at the specified frequency
- **Complex Tone**: Combines the fundamental frequency with harmonics (2nd, 3rd, 4th harmonics) for a richer sound
- **Envelope**: Complex tones include fade-in and fade-out to prevent clicking artifacts
- **Default Sample Rate**: 44100 Hz (CD quality)

## Requirements

- Python 3.7+
- numpy
- sounddevice
- typer[all]

## License

This project is provided as-is for educational and personal use.
