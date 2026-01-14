# Music Samples

This folder contains pre-made JSON files with musical sequences that can be played using the `play-file` command.

## Usage

```bash
# Play a sample file
python pysound.py play-file samples/music/c_major_scale.json

# Or use relative path
python pysound.py play-file samples/music/twinkle_twinkle.json
```

## Available Samples

- **c_major_scale.json** - Ascending C major scale (C4 to C5)
- **c_major_chord.json** - C major triad (C-E-G)
- **twinkle_twinkle.json** - First phrase of "Twinkle Twinkle Little Star"
- **happy_birthday.json** - First phrase of "Happy Birthday"
- **pentatonic_scale.json** - C major pentatonic scale
- **chord_progression.json** - I-V-vi-IV chord progression in C major
- **simple_beep.json** - Simple beep sequence for testing

## Creating Your Own

You can create your own JSON files following these formats:

### Simple Format
```json
{
  "name": "My Song",
  "description": "Description of the song",
  "notes": [261.63, 293.66, 329.63],
  "duration": 0.5,
  "pause": 0.1,
  "simple": false
}
```

### Detailed Format
```json
{
  "name": "My Song",
  "description": "Description of the song",
  "notes": [
    {"frequency": 440.0, "duration": 1.0, "pause": 0.2},
    {"frequency": 523.25, "duration": 0.5, "pause": 0.1}
  ],
  "simple": false
}
```

## Field Descriptions

- **name**: Display name for the sequence
- **description**: Optional description
- **notes**: Array of frequencies (simple) or note objects (detailed)
- **duration**: Default duration per note in seconds (simple format)
- **pause**: Default pause between notes in seconds (simple format)
- **simple**: Use simple sine wave (true) or complex tone (false)
- **sample_rate**: Optional sample rate (default: 44100)
