"""Push-to-talk recorder (Lane M, task M11).

    python3 voice/record.py out.wav

Press Enter to start, Enter again to stop. Writes 16 kHz mono 16-bit WAV, the format whisper-cli
needs. Uses the sounddevice package (in the stack, install with pip install sounddevice). The
import is lazy, so the rest of the voice code works without it.
"""
import sys
import wave

SAMPLE_RATE = 16000


def write_wav(path, samples, rate=SAMPLE_RATE):
    """samples: bytes of 16-bit little-endian mono PCM."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples)


def record_push_to_talk(path, input_fn=input, sd=None, print_fn=print):
    """Record from the default microphone between two Enter presses. Returns seconds recorded.

    input_fn and sd (the sounddevice module) can be replaced, which is how the tests run it.
    """
    if sd is None:
        try:
            import sounddevice as sd
        except ImportError:
            raise SystemExit("sounddevice is not installed: pip install sounddevice")
    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(bytes(indata))

    input_fn("Press Enter to start talking... ")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        print_fn("Recording. Press Enter to stop.")
        input_fn("")
    data = b"".join(chunks)
    write_wav(path, data)
    return len(data) / 2 / SAMPLE_RATE


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 voice/record.py out.wav")
    secs = record_push_to_talk(sys.argv[1])
    print(f"saved {sys.argv[1]} ({secs:.1f} s)")
