Test all 7 TTS engines with audio playback.

## Usage

Use this command to verify all TTS engines are working and hear audio output.

## Implementation

Run the comprehensive TTS engine test script:

```bash
python3 /home/pmoves/PMOVES.AI/pmoves/tools/test_all_tts_engines.py
```

### Options

Test without audio playback (save files only):
```bash
python3 /home/pmoves/PMOVES.AI/pmoves/tools/test_all_tts_engines.py --no-play
```

Test a specific engine:
```bash
python3 /home/pmoves/PMOVES.AI/pmoves/tools/test_all_tts_engines.py --engine kitten_tts
```

## The 7 TTS Engines

| Engine | ID | Default Voice |
|--------|-----|---------------|
| KittenTTS | `kitten_tts` | expr-voice-2-f |
| Kokoro TTS | `kokoro` | af_heart |
| F5-TTS | `f5_tts` | (reference audio) |
| IndexTTS2 | `indextts2` | (reference audio) |
| Fish Speech | `fish` | (reference audio) |
| ChatterboxTTS | `chatterbox` | (reference audio) |
| VoxCPM | `voxcpm` | (reference audio) |

## Expected Output

```
==================================================
 TTS Engine Test Suite
==================================================
Target: http://localhost:7861
Output: /tmp/pmoves-tts-test

Checking service health...
✓ Service is healthy

==================================================
 Loading TTS Models
==================================================
  Loading KittenTTS... ✓ (2.1s)
  Loading Kokoro TTS... ✓ (3.4s)
  Loading F5-TTS... ✓ (4.2s)
  Loading IndexTTS2... ❌ No module named 'omegaconf'
  Loading Fish Speech... ❌ not available
  Loading ChatterboxTTS... ❌ not available
  Loading VoxCPM... ❌ No module named 'voxcpm'

Models loaded: 3/7

==================================================
 Testing Synthesis
==================================================

[1/7] KittenTTS
      Synthesizing: "Hello! This is a test of the text to..."
      ✓ Generated 343,244 bytes in 2.3s
      📁 Saved: /tmp/pmoves-tts-test/kitten_tts.wav
      🔊 Playing audio...
      ✓ ffplay playback complete
      ✓ PowerShell playback complete

[2/7] Kokoro TTS
      Synthesizing: "Hello! This is a test of the text to..."
      ✓ Generated 287,532 bytes in 4.1s
      📁 Saved: /tmp/pmoves-tts-test/kokoro.wav
      🔊 Playing audio...
      ✓ ffplay playback complete
      ✓ PowerShell playback complete

...

==================================================
 Summary
==================================================
Engines working: 3/7

Audio files saved:
  ✓ /tmp/pmoves-tts-test/kitten_tts.wav
  ✓ /tmp/pmoves-tts-test/kokoro.wav
  ✓ /tmp/pmoves-tts-test/f5_tts.wav
```

## Audio Playback Methods

The script uses three playback methods:

1. **Save to file** - Always saves WAV to `/tmp/pmoves-tts-test/`
2. **ffplay** - Terminal audio playback (requires ffmpeg)
3. **PowerShell** - WSL2 host speakers via Windows

## Manual Playback

If automatic playback doesn't work, play files manually:

```bash
# Linux/ffplay
ffplay -nodisp -autoexit /tmp/pmoves-tts-test/kitten_tts.wav

# WSL2 via PowerShell
powershell.exe -c "(New-Object Media.SoundPlayer '\\wsl$\Ubuntu\tmp\pmoves-tts-test\kitten_tts.wav').PlaySync()"

# Copy to Windows
cp /tmp/pmoves-tts-test/*.wav /mnt/c/Users/$USER/Desktop/
```

## Notes

- Model loading can take 30-120 seconds per engine
- Some engines require GPU (will fall back to CPU)
- Reference audio engines (F5, Fish, VoxCPM) need voice samples for best results
- Audio files are 24kHz 16-bit mono WAV format
