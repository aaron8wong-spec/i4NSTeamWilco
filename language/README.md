# Language (R2)

- **5.5:** `make_grammar.py` builds `command.gbnf` from `$defs/Command` in the frozen `integration/schemas.json` (v1.0.0, see `docs/schemas.md`). Regenerate with `python3 language/make_grammar.py`. The grammar enforces integer ranges and the `place` / `event_id` patterns, but not lat/lon bounds (jsonschema checks those). Result on the frozen schema: Llama 3.2 3B Instruct Q4_K_M via llama.cpp 0.8.0 (brew, Metal with the workaround below) gave schema-valid JSON on 40/40 seeds (`language/results_5_5.csv`; temperature 0, one run, `python3 language/run_llm.py --seeds`), median latency 3.4 s. The action matched the seed on 35/40, informational only. This is a format check, not accuracy.
- **5.6:** `data/seeds.jsonl` holds 40 seed commands (32 valid, 8 `clarify`), migrated to schema v1.0.0. Every seed is checked against the schema by `language/test_language.py`.

Run the tests: `cd language && python3 -m pytest -q` (needs `pytest` and `jsonschema`). The 40 grammar-acceptance tests are skipped unless llama.cpp's `llama-gbnf-validator` is on PATH.

Run the model: `GGML_METAL_BF16_DISABLE=1 llama-server -m ~/models/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8080 -c 4096`.

Metal note (M2, macOS 15.6, llama.cpp 0.8.0 from brew): without the variable, the Metal shader build fails (`constexpr` error in the `unary` kernel) and the server cannot start on the GPU. Setting `GGML_METAL_BF16_DISABLE=1` lets it start with no Metal errors, and a short `hold` request ran at about 34 tokens/s generation, against about 4 on CPU (`--device none`). We did not find out why the fix works, and the server log has no Metal lines, so GPU use is inferred from speed. Over the 40 seeds the median latency stayed about 6 s (CPU 6.4 s, GPU 6.0 s). The laptop was swapping heavily (16 GB), so treat all latency numbers as a worst case.
