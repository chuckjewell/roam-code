"""Tests for hypergraph benchmark helpers."""

from roam.benchmarks.hypergraph import (
    compute_timing_delta,
    run_synthetic_recurring_set_benchmark,
)


def test_compute_timing_delta_calculates_percent_change():
    baseline = {
        "map_json": {"ms": 100.0},
        "coupling_json": {"ms": 50.0},
    }
    current = {
        "map_json": {"ms": 110.0},
        "coupling_json": {"ms": 45.0},
    }
    delta = compute_timing_delta(baseline, current)

    assert delta["map_json"]["baseline_ms"] == 100.0
    assert delta["map_json"]["current_ms"] == 110.0
    assert delta["map_json"]["delta_pct"] == 10.0
    assert delta["coupling_json"]["delta_pct"] == -10.0


def test_synthetic_benchmark_detects_recurring_three_file_set():
    result = run_synthetic_recurring_set_benchmark()

    assert result["set_mode_count"] >= 1
    assert result["abc_set"] is not None
    assert result["abc_set"]["occurrences"] >= 2
