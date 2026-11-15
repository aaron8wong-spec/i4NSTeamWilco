# Voice (R3)
 
- **5.7:** Built whisper.cpp (commit `727d3e76`) on a MacBook Air (Apple M1, 8 GB, macOS 13.0) with model `base.en` (141 MB). Transcribed 10 clips: 5 spoken commands recorded once in a quiet room, plus a noisy copy of each made by mixing in pink noise. Result: 7/10 exact matches (noisy 4/5, quiet 3/5). Word error rate 12.1% overall (7/58 words): noisy 3.4% (1/29), quiet 20.7% (6/29). Words were compared after lowercasing and removing punctuation; WER uses jiwer. One speaker, one run, CPU defaults. Latency was not measured. This is not a field accuracy claim.
## Files
 
| Path | What it is |
|---|---|
| `voice/clips/` | Original recordings (`.m4a`, quiet room) |
| `voice/clips_wav/` | 16 kHz mono 16-bit WAVs fed to whisper: `*_quiet.wav` (converted originals) and `*_noisy.wav` (quiet + added noise) |
| `voice/transcripts/` | whisper.cpp output, one `.txt` per WAV |
| `voice/results_5_7.csv` | Expected text vs. transcript, exact match, word errors, WER per clip |
 
The 5 commands: "Loiter over the red truck." / "Take off and hover at 20 meters." / "Search the North Yard for vehicles." / "Return home." / "Fly to the east edge of the tree line."
 
## Setup
 
Tested on macOS 13.0 (Apple M1). whisper.cpp and the model are **not** in this repo; clone them anywhere outside it.
 
1. Install the tools. We used conda (cmake 4.3.1, ffmpeg 8.0.1); Homebrew should also work (`brew install cmake ffmpeg`).
```
conda install -c conda-forge cmake ffmpeg
```
2. Get whisper.cpp at the same commit we used:
```
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
git checkout 727d3e76
```
3. Download the model (about 141 MB, saved to `models/ggml-base.en.bin`):
```
sh ./models/download-ggml-model.sh base.en
```
4. Build (default CMake options, no extra flags):
```
cmake -B build
cmake --build build -j --config Release
```
5. Check the build on the bundled sample:
```
./build/bin/whisper-cli -m models/ggml-base.en.bin -f samples/jfk.wav
```
 
For newer versions, follow the Quick start in https://github.com/ggml-org/whisper.cpp.
 
## Parameters we used
 
| Setting | Value | Notes |
|---|---|---|
| whisper.cpp commit | `727d3e76` | |
| Model | `ggml-base.en.bin` | English-only base model, 141 MB |
| Hardware | Apple M1, 8 GB RAM | Laptop, default threads |
| Audio format | 16 kHz, mono, 16-bit PCM WAV | `-ar 16000 -ac 1 -c:a pcm_s16le`; whisper-cli needs 16-bit WAV |
| Output | `-otxt -of transcripts/<clip>` | Plain text, no timestamps |
| Noise added | pink noise, amplitude 0.05, 16 kHz | ffmpeg `anoisesrc` |
| Other decoding settings | whisper-cli defaults | No language, beam, temperature or thread flags set |
 
## How to reproduce
 
Run from the `whisper.cpp` folder, with the clips in `clips/` there.
 
1. Convert the recordings:
```
mkdir -p clips_wav transcripts
for f in clips/*.m4a; do
  ffmpeg -i "$f" -ar 16000 -ac 1 -c:a pcm_s16le "clips_wav/$(basename "${f%.*}").wav"
done
```
2. Make the noisy copies:
```
for i in 01 02 03 04 05; do
  ffmpeg -i clips_wav/clip${i}_quiet.wav -f lavfi -i "anoisesrc=color=pink:amplitude=0.05:sample_rate=16000" \
    ____
done
```
3. Transcribe every WAV:
```
for f in clips_wav/*.wav; do
  ./build/bin/whisper-cli -m models/ggml-base.en.bin -f "$f" -otxt -of "transcripts/$(basename "${f%.wav}")"
done
```
 
## What went wrong
 
The noisy clips are the quiet recordings with noise added, so both versions contain the same speech. That makes the misses below model behavior, not missing audio.
 
- `clip04_quiet` ("Return home.") came back as `[BLANK_AUDIO]`, but its noisy copy transcribed perfectly. whisper.cpp decided the clean clip was silence. A likely cause is a very short command with a lot of silence around it; not yet tested.
- `clip05_quiet` dropped "Fly to" and wrote "treeline" for "tree line." The noisy copy kept those words but heard "Fly" as "high."
- The opening verb decides the drone action, so "Fly" lost or misheard is the error that matters most for us.
Quiet scoring worse than noisy is unexpected, and with 5 clips per condition it is not a real comparison. Task 6.7 (30 clips, 10 noisy, more speakers if possible) should test it properly, including trimming silence and very short commands.
