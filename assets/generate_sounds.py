"""Generate simple beep sound effects as WAV files."""

import struct
import wave
import math

SAMPLE_RATE = 44100


def generate_tone(frequency, duration_ms, volume=0.5):
    """Generate a sine wave tone."""
    n_samples = int(SAMPLE_RATE * duration_ms / 1000)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        # Apply fade in/out to avoid clicks
        envelope = 1.0
        fade_samples = int(SAMPLE_RATE * 0.005)  # 5ms fade
        if i < fade_samples:
            envelope = i / fade_samples
        elif i > n_samples - fade_samples:
            envelope = (n_samples - i) / fade_samples
        value = volume * envelope * math.sin(2 * math.pi * frequency * t)
        samples.append(int(value * 32767))
    return samples


def save_wav(filename, samples):
    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for s in samples:
            wf.writeframes(struct.pack("<h", max(-32768, min(32767, s))))


# Start sound: short high beep (800Hz, 80ms)
start_samples = generate_tone(800, 80, volume=0.4)
save_wav("sound_start.wav", start_samples)
print("Generated sound_start.wav")

# Done sound: two quick beeps (1000Hz, 60ms each, 40ms gap)
done_samples = generate_tone(1000, 60, volume=0.4)
done_samples += [0] * int(SAMPLE_RATE * 0.04)  # 40ms silence
done_samples += generate_tone(1200, 60, volume=0.4)
save_wav("sound_done.wav", done_samples)
print("Generated sound_done.wav")
