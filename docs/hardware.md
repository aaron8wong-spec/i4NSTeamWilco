# Hardware table

Every performance cell says "not measured" until someone runs `language/bench.py` on that machine and pastes the output. Never fill a cell from memory or from a spec sheet.

## Table

| Device | RAM | Accelerator | Model + quant | Tokens/s | Time to first output | Whisper RTF | Power |
|---|---|---|---|---|---|---|---|
| Mac (MacBook Air, Apple M2, 8 cores: 4 performance + 4 efficiency) | 16 GB | Apple M2 integrated GPU (Metal) | not measured | not measured | not measured | not measured | not measured |
| Lane S WSL2 machine | not measured | not measured | not measured | not measured | not measured | not measured | not measured |

Device facts for the Mac row were read from the machine on 2026-11-20 with `sysctl -n machdep.cpu.brand_string hw.memsize` and `system_profiler SPHardwareDataType`. The number of GPU cores was not read. Lane S fills his own row (task S12): device, RAM, accelerator, model and quantization.

## How measured

See `language/bench.py` (task M14, written, not yet run on real hardware). It prints tokens per second, time to first output and whisper real-time factor for the same model file, the same prompt and 10 commands, with 3 runs and the first run thrown away.

Rules for filling the table:

- Both machines use the same model file and the same prompts. Write the model name and quantization in the table.
- Paste the exact command and its output next to the table or in the commit message.
- Whisper RTF means processing time divided by audio length. Write the whisper model size.
- Time to first output is measured from sending the prompt to the first token.
- Power: "not measured" unless a wall meter was used. If one was, write the meter, the idle reading and the load reading.
- Latency numbers from earlier runs (3 to 6 s per command) came from a swapping 16 GB laptop. They are a worst case and are not in this table.
- This table says nothing about alternative edge chips. That is roadmap, not MVP.
