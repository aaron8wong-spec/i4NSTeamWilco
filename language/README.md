# Language (R2)

- **5.5 (in progress):** `schema_to_gbnf.py` builds `command.gbnf` from `schemas.json`. Regenerate with `python3 language/schema_to_gbnf.py`. `schemas.json` here is a local placeholder copied from CLAUDE.md section 5 until R5's frozen version lands. Result: Llama 3.2 3B Instruct Q4_K_M via llama.cpp 0.8.0 (brew, CPU only) gave schema-valid JSON on 40/40 seeds (`language/results_5_5.csv`; temperature 0, one run, `python3 language/run_llm.py --seeds`). This is a format check only, not accuracy.
- **5.6:** `data/seeds.jsonl` holds 40 seed commands (32 valid, 8 `clarify`). Every seed is checked against the schema by `language/test_language.py`.

Run the tests: `cd language && python3 -m pytest -q` (needs `pytest` and `jsonschema`). The 40 grammar-acceptance tests are skipped unless llama.cpp's `llama-gbnf-validator` is on PATH.

Run the model: `llama-server -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096 --device none`. `--device none` is needed on the M2 because the Metal shader build fails in llama.cpp 0.8.0 on this macOS. Latency numbers in the CSV were taken under heavy memory swapping on a 16 GB laptop, so treat them as a worst case.
