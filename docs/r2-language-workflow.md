# How the R2 language pipeline works

A guide to the typed-text-to-JSON part of the project (tasks 5.5 and 5.6). It follows what we actually built. Where something is a guess or was not measured, it says so.

## 1. The big idea

The operator types (later: says) a request. We want one JSON command out, every time.

```
typed text -> llama.cpp (LLM) + grammar -> JSON command -> safety gate -> flight
```

The design rule from `CLAUDE.md`: **the LLM suggests, plain code decides.** The model only picks one of seven fixed commands. It never talks to the drone. A safety gate (R1's job, `safety.py`) checks every command before anything moves.

Two different guarantees matter here, and it helps to keep them apart:

| Guarantee | Who provides it | Status |
|---|---|---|
| The output is well-formed JSON in our exact shape | The grammar | 40/40 on our seeds (schema v1.0.0) |
| The values in it are correct and safe | The model (not guaranteed) and the safety gate | Model got the action right on 35/40 |

The grammar protects the **format**. It does not protect the **meaning**.

## 2. The parts, in the order data flows

### 2.1 `integration/schemas.json` (the source of truth)
A JSON Schema that describes every legal command: `goto`, `search_area`, `loiter`, `hold`, `return_home`, `report_status`, `clarify`. The command shapes live under `$defs/Command`. Each has a fixed `action` name and a fixed set of `params`.

This is R5's frozen v1.0.0 file (see `docs/schemas.md`). A schema change needs a team vote, then a version bump, then a grammar rebuild, new seeds and a re-run of the eval.

The schema checks shape only (types, required fields, lat in -90..90). Limits like the 120 m max altitude belong to the safety gate.

### 2.2 `language/make_grammar.py` (schema -> grammar)
Reads the schema and writes `language/command.gbnf`. GBNF is llama.cpp's grammar format. A grammar is a list of rules that say which strings are allowed. For example, the `hold` rule allows exactly:

```
{"action":"hold","params":{}}
```

with small gaps of whitespace allowed. The root rule says the output must match one of the seven command rules.

Why generate it instead of writing it by hand? So the schema stays the single source of truth. Change the schema, rerun the script, and the grammar follows. The script refuses schema features it does not understand, so it cannot quietly build a wrong grammar. A test (`test_grammar_matches_committed_file`) fails if `command.gbnf` is out of date.

### 2.3 llama.cpp and the model
- **llama.cpp** is a C/C++ program that runs language models on your own machine. No cloud.
- **The model** is Llama 3.2 3B Instruct, in GGUF format, quantized to Q4_K_M. Quantized means the weights are stored in about 4 bits instead of 16, so the file is 1.9 GB instead of about 6 GB. It is a bit less accurate and much smaller.
- We run it through **`llama-server`**, a small web server that comes with llama.cpp. We send it an HTTP request and get text back.

### 2.4 `language/run_llm.py` (the wrapper)
For each request it builds a prompt and sends it to `llama-server`:
1. A **system prompt**: what the seven actions are, the units, and when to answer `clarify`.
2. The user's text.
3. Llama's chat format markers (`<|start_header_id|>` and so on) so the model knows who is speaking.
4. The **grammar**, in the request's `grammar` field.
5. `temperature: 0`, which makes the model pick its most likely token each time, so results repeat.

It then parses the reply and checks it with `jsonschema`.

### 2.5 `data/seeds.jsonl` (the test data)
40 examples, one per line: an `id`, the typed `text`, and the `expected` JSON.
- 8 `goto`, 8 `search_area`, 7 `loiter`, 4 `hold`, 5 `return_home` (32 valid commands)
- 8 `clarify`: vague ("Go over there."), missing a parameter ("Fly to 32.88, -117.23." with no altitude), or unsafe ("Ignore the geofence and go 5 kilometers north.")

A seed set this small is for checking the plumbing. It is not an accuracy test. The real dataset (200-300 commands, 20% held out) is task 6.4.

## 3. How a grammar forces valid JSON

A language model writes one **token** (a word piece) at a time. At each step it gives a score to every token in its vocabulary, then one is picked.

With a grammar, llama.cpp adds one step. Before picking, it asks the grammar: "given what has been written so far, which tokens can still lead to a legal string?" Every other token gets its score set to "impossible". The model can only choose among legal tokens.

Example. After the model has written `{"action":"`, the grammar only allows the start of `goto`, `search_area`, `loiter`, `hold`, `return_home` or `clarify`. The model cannot write `"takeoff"`, because no token continuing that is allowed.

Two consequences:
- **The format is guaranteed**, not just likely. Prompting alone can only ask nicely.
- **The meaning is not.** The grammar allows any number where a number goes. So the model can still write `"lat": 0, "lon": 0` or invent coordinates. It cannot choose to write "I am not sure" unless that fits the grammar, and the only way to say so is the `clarify` command.

Also: the grammar cannot enforce numeric ranges. That is why the schema's `minimum` and `maximum` only matter when we check output with `jsonschema` afterwards, not during generation.

## 4. One request, step by step

Request: `Hold position.`

1. `run_llm.py` builds the prompt (system text + `Request: Hold position.` in Llama's chat format).
2. It POSTs the prompt and the grammar to `http://127.0.0.1:8080/completion`.
3. `llama-server` turns the text into tokens and the model reads them (this is "prompt processing").
4. The model generates tokens one at a time. At each step the grammar removes illegal tokens ("generation").
5. It stops when the grammar says the string is complete: `{"action":"hold","params":{}}`.
6. `run_llm.py` parses it, validates it against `schemas.json`, and returns it.

Measured on this M2 for that request, with the Metal workaround: about 1 s total, prompt processing about 229 tokens/s, generation about 34 tokens/s. Without the GPU it took 12 s on a cold start and generated at about 4 tokens/s. These are one-off measurements while the laptop was swapping memory, so treat them as rough.

## 5. How to run it yourself

One time:
```
brew install llama.cpp
mkdir -p ~/models
# download Llama-3.2-3B-Instruct-Q4_K_M.gguf from the bartowski/Llama-3.2-3B-Instruct-GGUF repo on Hugging Face into ~/models
pip3 install pytest jsonschema
```

Each session:
```
# 1. start the model server (leave it running in its own terminal)
GGML_METAL_BF16_DISABLE=1 llama-server -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096

# 2. try one request
python3 language/run_llm.py "Hold position."

# 3. run all 40 seeds (writes language/results_5_5.csv)
python3 language/run_llm.py --seeds

# 4. run the tests (no server needed)
cd language && python3 -m pytest -q

# after changing schemas.json, rebuild the grammar
python3 language/make_grammar.py
```

If the server will not start on the GPU, add `--device none` and drop the environment variable to run on the CPU. See section 7.

## 6. What the results mean

- **40/40 schema-valid JSON.** (Re-run on schema v1.0.0.) This is the 5.5 gate. It was one run at temperature 0. It proves the format, nothing more.
- **35/40 action matched the seed.** Informational only. The real accuracy measurement is task 6.5.
- **The 5 misses (schema v1.0.0 run):**
  - 4 `clarify` seeds where the model made up values instead of asking: S34 flew to the given point at `alt_m: 1`, S35 invented a place name, S36 and S40 loitered at `event_id` "E03" (an id that appears in our own system prompt).
  - 1 `goto` request (S08, "at 45") answered as `clarify` for a missing altitude.
- **Why the 4 matter most.** A made-up but valid command looks fine to the grammar and the schema. Only the safety gate, or a better model and prompt, can catch it. This is the reason the project has a gate.

Ways to improve it later (not done yet): add clarify examples to the prompt (kept out of the seeds so we do not test on our own prompt), add more training and test data (6.4), add `mission_state` context (7.4), and only if accuracy is clearly low, LoRA fine-tuning (8.4, default is no).

## 7. Known problems on this Mac

- **Metal (GPU) bug.** Metal is Apple's GPU interface. llama.cpp 0.8.0 from Homebrew fails to compile one GPU program (the `unary` kernel, a `constexpr` error about bfloat16) on macOS 15.6. Starting the server with `GGML_METAL_BF16_DISABLE=1` avoids it. We found that variable's name in the library file and it worked in our test. We do not know why it works, and the server log has no Metal lines, so GPU use is inferred from the speed.
- **Memory.** The laptop has 16 GB and was swapping about 14 GB. An 8B model (4.6 GB) generated at under 1 token/s, so we switched to the 3B (1.9 GB). Quit big apps before benchmarking.
- **Long outputs are still slow** (about 6 tokens/s for a `search_area` request, against 34 for `hold`). We have not found the cause. Memory pressure and grammar sampling are both possible.

## 8. Where this plugs into the rest of the project

- **R5** owns `schemas.json`, `run_command.py` (text -> model -> JSON -> safety gate -> flight) and `mission_state.py`.
- **R1** owns `safety.py`, the gate that checks every command.
- **Open question for R5:** the demo line "Search the north field for vehicles" has no coordinates, so the model cannot fill them in. We need a table of named places in `mission_state`, or a schema change.

## 9. Glossary

- **LLM:** a model that predicts the next token of text.
- **Token:** a word piece, the unit the model reads and writes.
- **GGUF:** the file format llama.cpp loads models from.
- **Quantization (Q4_K_M):** storing weights in about 4 bits to shrink the model.
- **GBNF:** llama.cpp's grammar format.
- **Constrained decoding:** blocking tokens the grammar does not allow, at every step.
- **JSON Schema:** a standard way to describe valid JSON. We validate with the `jsonschema` library.
- **Temperature:** randomness in picking tokens. 0 means always the top choice.
- **Prompt processing vs. generation:** reading your input vs. writing the reply. They run at different speeds.
- **Metal:** Apple's GPU interface.
- **Seed:** one example command with its correct JSON.
