import subprocess
from pathlib import Path

WHISPER_BIN = Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli"
MODEL_PATH = Path.home() / "whisper.cpp" / "models" / "ggml-base.en.bin"

def transcribe(wav_path: str | Path) -> str:
    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise FileNotFoundError(f"Audio file not found: {wav_path}")
    cmd = [
        str(WHISPER_BIN),
        "-m", str(MODEL_PATH),
        "-f", str(wav_path),
        "--no-timestamps",
        "-nt"
      ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

    if __name__ == "__main__":
        import sys
        sample = Path.home() / "whisper.cpp" / "samples" / "jfk.wav"
        test_file = sys.argv[1] if len(sys.argv) > 1 else str(sample)
        print("Transcribing:", test_file)
        print("Output:", transcribe(test_file))
