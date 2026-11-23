"""Speech to text with whisper.cpp (Lane M, task M11).

    from transcribe import transcribe
    text = transcribe("clip.wav")

Calls the whisper-cli binary, so nothing here talks to the cloud. Paths come from the environment
(WHISPER_CLI, WHISPER_MODEL) or the defaults below (whisper.cpp cloned to ~/whisper.cpp, see
voice/README.md). The audio must be 16 kHz mono 16-bit WAV.

Whisper writes tags like [BLANK_AUDIO] or (wind blowing) when it hears no speech. clean() removes
them, so silence gives an empty string. Callers (task M12) ignore an empty transcript.
"""
import os
import re
import subprocess
from pathlib import Path

DEFAULT_CLI = Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli"
DEFAULT_MODEL = Path.home() / "whisper.cpp" / "models" / "ggml-base.en.bin"

_TAG = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")


class TranscribeError(RuntimeError):
    pass


def cli_path():
    return Path(os.environ.get("WHISPER_CLI", DEFAULT_CLI))


def model_path():
    return Path(os.environ.get("WHISPER_MODEL", DEFAULT_MODEL))


def model_name():
    """Model file name, written next to every error rate (for example ggml-base.en.bin)."""
    return model_path().name


def clean(raw):
    """Remove whisper's sound tags and extra spaces. Returns '' when nothing was said."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", raw)).strip()


def transcribe(wav, cli=None, model=None, timeout_s=60):
    """Return the cleaned transcript of a WAV file. Raises TranscribeError if whisper fails."""
    cli, model = Path(cli or cli_path()), Path(model or model_path())
    if not Path(wav).is_file():
        raise TranscribeError(f"audio file not found: {wav}")
    if not cli.is_file():
        raise TranscribeError(f"whisper-cli not found at {cli} (set WHISPER_CLI, see voice/README.md)")
    if not model.is_file():
        raise TranscribeError(f"whisper model not found at {model} (set WHISPER_MODEL)")
    try:
        # -nt: no timestamps. -np: print only the result.
        run = subprocess.run([str(cli), "-m", str(model), "-f", str(wav), "-nt", "-np"],
                             capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        raise TranscribeError(f"whisper-cli timed out after {timeout_s} s") from e
    if run.returncode != 0:
        raise TranscribeError(f"whisper-cli failed ({run.returncode}): {run.stderr.strip()[:200]}")
    return clean(run.stdout)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("usage: python3 voice/transcribe.py clip.wav")
    print(transcribe(sys.argv[1]))
