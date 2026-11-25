"""Latency harness: percentile maths, the report's numbers, the metrics contract, the scripted run, spend."""
import pytest

from jarvis.health.latency import (
    LatencyRecorder,
    TurnTrace,
    build_report,
    load_traces,
    percentile,
    to_metrics_latency,
)
from jarvis.health.scripted import run_scripted_sync
from jarvis.health.spend import Prices, SpendMeter
from tools.latency_report import main as report_main


def test_percentile_matches_linear_interpolation():
    xs = [10, 20, 30, 40, 50]
    assert percentile(xs, 50) == 30
    assert percentile(xs, 95) == pytest.approx(48.0)
    assert percentile([7], 95) == 7
    assert percentile(list(range(1, 101)), 95) == pytest.approx(95.05)


def known_traces():
    out = []
    for i in range(1, 21):  # chat turns: STT i*10, route +1, first token +400, TTS +200, out +50
        stt = 10.0 * i
        out.append(TurnTrace(f"c{i}", "t1", {"vad_end": 0.0, "stt_final": stt, "route": stt + 1,
                                              "llm_first_token": stt + 401, "tts_first_byte": stt + 601,
                                              "audio_out": stt + 651}, {"speculation": "hit" if i % 4 else "miss"}))
    for i in range(1, 11):  # commands: route i ms, cached phrase 5 ms later, sound 2 ms later
        out.append(TurnTrace(f"k{i}", "t0", {"vad_end": 0.0, "route": float(i), "tts_first_byte": i + 5.0,
                                              "audio_out": i + 7.0}, {"routed_on_partial": True}))
    return out


def test_report_numbers():
    r = build_report(known_traces())
    assert r.turns == {"t1": 20, "t0": 10}
    stt = r.row("t1", "stt_final")
    assert (stt.p50_ms, stt.p95_ms) == (pytest.approx(105.0), pytest.approx(190.5))
    think = r.row("t1", "llm_first_token")
    assert (think.step_p50_ms, think.step_p95_ms) == (400.0, 400.0)
    assert r.row("t1", "tts_first_byte").step_p50_ms == 200.0
    route = r.row("t0", "route")
    assert (route.p50_ms, route.p95_ms) == (pytest.approx(5.5), pytest.approx(9.55))
    assert r.totals["t1"]["p50"] == pytest.approx(756.0) and r.totals["t1"]["ok"] == 1.0
    assert r.totals["t0"]["p95"] == pytest.approx(16.55)
    assert r.notes["speculation_hit_rate"] == pytest.approx(0.75)


def test_metrics_rows_follow_the_contract(contract):
    rows = to_metrics_latency(build_report(known_traces()))
    assert contract("metrics", {"latency": rows}) == []
    assert [r["stage"] for r in rows][0] == "Hear (speech to text)"


def test_recorder_writes_ids_and_timings_only(tmp_path):
    t = [0.0]
    rec = LatencyRecorder(clock=lambda: t[0], sink=tmp_path / "latency.jsonl")
    rec.mark("turn-1", "vad_end")
    t[0] = 0.25
    rec.mark("turn-1", "stt_final")
    rec.mark("turn-1", "stt_final", 9.0)  # the first mark wins
    rec.finish("turn-1")
    rec.mark("turn-1", "audio_out")       # late marks don't reopen a finished turn
    assert rec.finish("turn-1") is None
    (trace,) = load_traces(tmp_path / "latency.jsonl")
    assert trace.ms == {"vad_end": 0.0, "stt_final": 250.0}
    assert set((tmp_path / "latency.jsonl").read_text().split('"')) >= {"turn", "kind", "ms", "notes"}


def test_fifty_utterance_scripted_run_produces_a_report(capsys):
    res = run_scripted_sync(50, scale=0.05)
    assert res.turns == 50 and sum(res.report.turns.values()) >= 45  # silent commands have no audio stage
    for stage in ("stt_final", "route", "llm_first_token", "tts_first_byte", "audio_out"):
        assert res.report.row("t1", stage) is not None
    assert res.speculation["spec_cancelled"] >= 1 and res.speculation["spec_hit"] >= 1
    assert res.spend["credits"]["elevenlabs_left"] < res.spend["credits"]["elevenlabs_total"]


def test_report_tool_reads_a_trace_file(tmp_path, capsys):
    p = tmp_path / "latency.jsonl"
    p.write_text("\n".join(t.to_json() for t in known_traces()), encoding="utf-8")
    assert report_main(["--from", str(p), "--strict"]) == 0
    out = capsys.readouterr().out
    assert "chat end of speech -> first sound: p50 756.0 ms" in out


def test_spend_meter():
    alerts = []
    m = SpendMeter(Prices(monthly_cap_usd=0.01), on_alert=lambda usd, cap: alerts.append((usd, cap)))
    usd = m.record_llm("claude-haiku-5-5", {"input_tokens": 1000, "output_tokens": 200,
                                            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 2000})
    assert usd == pytest.approx((1000 * 1.0 + 200 * 5.0 + 2000 * 0.10) / 1e6)
    assert m.record_tts("eleven_flash_v2_5", 100) == 50.0
    assert m.to_metrics()["credits"] == {"elevenlabs_left": 29950.0, "elevenlabs_total": 30000}
    assert len(alerts) == 1  # 70 % of the cap passed once, alerted once
    m.record_tts("eleven_flash_v2_5", 100)
    assert len(alerts) == 1
    with pytest.raises(KeyError):
        m.record_llm("unknown-model", {})
