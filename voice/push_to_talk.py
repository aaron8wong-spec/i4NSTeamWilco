import subprocess
import sys
from pathlib import Path
from transcribe import transcribe

def main():
    audio_path = Path("voice/live_command.wav")

    print("\n" + "=" * 55)
    print("  4NS Army-737: Voice-to-Flight Push-to-Talk")
    print("=" * 55)

    input("\n[>] Press [ENTER] to start speaking...")
    print("\n>>> RECORDING... (Speak your flight command now!)")

    # Start live microphone recording
    proc = subprocess.Popen([
        "parecord",
        "--channels=1",
        "--rate=16000",
        "--format=s16le",
        "--file-format=wav",
        str(audio_path)
    ])

    input(">>> Press [ENTER] when you are finished speaking...\n")
    proc.terminate()
    proc.wait()

    print("[1/3] Transcribing with whisper.cpp...")
    spoken_text = transcribe(audio_path)
    print(f'   -> Heard: "{spoken_text}"')

    if not spoken_text.strip():
        print("[!] No speech detected. Please try again.")
        return

    print("\n[2/3] Routing command through llama.cpp + Safety Gate...")
    cmd = [
        "python3", "integration/run_command.py",
        "--text", spoken_text,
        "--llm", "http://127.0.0.1:8080"
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    main()