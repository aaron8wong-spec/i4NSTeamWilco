import bench


def test_summarize_drops_first_run():
    s = bench.summarize([100.0, 10.0, 20.0, 30.0])
    assert s["median"] == 20.0 and s["n"] == 3 and s["min"] == 10.0 and s["max"] == 30.0


def test_summarize_empty_or_single_run():
    assert bench.summarize([5.0]) is None
    assert bench.summarize([]) is None
    assert bench.summarize([5.0], drop_first=False)["median"] == 5.0


def test_tokens_per_second_and_rtf():
    assert bench.tokens_per_second(50, 2.0) == 25.0
    assert bench.tokens_per_second(0, 2.0) is None
    assert bench.tokens_per_second(10, 0) is None
    assert bench.rtf(3.0, 6.0) == 0.5
    assert bench.rtf(1.0, 0) is None


def test_quant_from_name():
    assert bench.quant_from_name("Llama-3.2-3B-Instruct-Q4_K_M.gguf") == "Q4_K_M"
    assert bench.quant_from_name("model.gguf") is None
    assert bench.quant_from_name(None) is None


def test_format_row_with_numbers():
    row = bench.format_row("dev", "16 GB", "m.gguf", "Q4_K_M",
                           {"median": 33.14}, {"median": 0.512}, {"median": 0.4})
    assert row == "| dev | 16 GB | m.gguf | Q4_K_M | 33.1 | 0.51 s | 0.40 |"


def test_format_row_not_measured():
    row = bench.format_row("dev", None, None, None, None, None, None, "whisper binary not found")
    assert row.count("not measured") == 6
    assert "whisper binary not found" in row


def test_whisper_not_measured_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("WHISPER_BIN", raising=False)
    monkeypatch.setattr(bench.shutil, "which", lambda n: None)
    r, why = bench.bench_whisper(None, None, None, 3)
    assert r is None and "binary" in why
    fake = tmp_path / "whisper-cli"
    fake.write_text("")
    r, why = bench.bench_whisper(str(fake), str(tmp_path / "nope.bin"), None, 3)
    assert r is None and "model" in why


def test_main_prints_not_measured_without_server(capsys, monkeypatch):
    monkeypatch.delenv("WHISPER_BIN", raising=False)
    monkeypatch.setattr(bench.shutil, "which", lambda n: None)
    bench.main(["--llm", "http://127.0.0.1:1", "--runs", "2"])
    out = capsys.readouterr().out
    assert "not measured" in out and "| Device |" in out
