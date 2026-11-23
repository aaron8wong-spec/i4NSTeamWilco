# Hardware table

Every performance cell says "not measured" until someone runs `language/bench.py` on that machine and pastes the output. Never fill a cell from memory or from a spec sheet.

## Table

| Device | RAM | Accelerator | Model + quant | Tokens/s | Time to first output | Whisper RTF | Power |
|---|---|---|---|---|---|---|---|
| Mac (MacBook Air, Apple M2, 8 cores: 4 performance + 4 efficiency) | 16 GB | Apple M2 integrated GPU (Metal) | Llama-3.2-3B-Instruct, Q4_K_M; whisper `ggml-base.en` | 3.0 (end to end, see notes) | 4.67 s (no prompt cache) | 0.06 | not measured |
| Lane S WSL2 machine | not measured | not measured | not measured | not measured | not measured | not measured | not measured |

Device facts for the Mac row were read from the machine on 2026-11-20 with `sysctl -n machdep.cpu.brand_string hw.memsize` and `system_profiler SPHardwareDataType`. The number of GPU cores was not read. Lane S fills his own row (task S12): device, RAM, accelerator, model and quantization.

## Mac row: how it was measured (2026-11-23)

Command: `python3 language/bench.py --llm http://127.0.0.1:8080 --whisper-bin ~/whisper.cpp/build/bin/whisper-cli --whisper-model ~/whisper.cpp/models/ggml-base.en.bin --wav voice/clips_wav/v01_quiet.wav`

Output: 3 runs of 10 commands each (223 tokens per run); run 1 discarded. Run 2: 74.9 s, run 3: 75.2 s. Tokens/s 3.0, time to first token 4.67 s, whisper real-time factor 0.06 (one call on a 6.9 s clip, includes model load).

Read these numbers with care:

- **Memory pressure.** Swap was about 9.3 GB of 10 GB used before and after the run (`sysctl vm.swapusage`). The machine was swapping, so these are a worst case, not a statement about the M2.
- **Tokens/s is end to end.** It is generated tokens divided by total wall time including prompt processing, with the prompt cache turned off. The prompt now has a few-shot block, so prompt processing is a large share. It is not pure decode speed.
- **The cache matters.** In `language/eval.py` (prompt cache on, same machine, same session) the median time per command was 2.1 s (train split, 212 commands). That is a different measurement and not comparable to the 3.0 tokens/s.
- One run, one machine, one model. Power was not measured.

## How measured

See `language/bench.py` (task M14; run once on the Mac, see above). It prints tokens per second, time to first output and whisper real-time factor for the same model file, the same prompt and 10 commands, with 3 runs and the first run thrown away.

Rules for filling the table:

- Both machines use the same model file and the same prompts. Write the model name and quantization in the table.
- Paste the exact command and its output next to the table or in the commit message.
- Whisper RTF means processing time divided by audio length. Write the whisper model size.
- Time to first output is measured from sending the prompt to the first token.
- Power: "not measured" unless a wall meter was used. If one was, write the meter, the idle reading and the load reading.
- Latency numbers from earlier runs (3 to 6 s per command) came from a swapping 16 GB laptop. They are a worst case and are not in this table.
- This table says nothing about alternative edge chips. That is roadmap, not MVP.
