"""Tests for AI benchmark reporting utilities."""

from __future__ import annotations

import csv
import json

import pytest

from swos420.ai.benchmark import (
    BenchmarkError,
    decode_flat_action,
    run_benchmark,
    write_benchmark_report,
)


def test_decode_flat_action_rejects_wrong_shape() -> None:
    with pytest.raises(BenchmarkError, match="Expected 13 action components"):
        decode_flat_action([0, 1, 2])


def test_run_benchmark_random_vs_heuristic() -> None:
    report = run_benchmark(
        policies=["random", "heuristic"],
        seasons=2,
        num_teams=4,
        seed=17,
    )

    assert report["config"]["seasons"] == 2
    assert report["config"]["num_teams"] == 4
    assert set(report["results"].keys()) == {"random", "heuristic"}

    for policy in ("random", "heuristic"):
        payload = report["results"][policy]
        seasons = payload["seasons"]
        summary = payload["summary"]

        assert len(seasons) == 2
        assert summary["reward_std"] >= 0.0
        assert sum(summary["champion_distribution"].values()) == 2

        for season in seasons:
            assert season["matchdays"] == 6
            assert len(season["cumulative_rewards"]) == 4
            assert season["champion"] is not None
            assert season["table"][0]["code"] == season["champion"]["code"]


def test_write_benchmark_report_outputs_json_and_csv(tmp_path) -> None:
    report = run_benchmark(
        policies=["random"],
        seasons=1,
        num_teams=4,
        seed=21,
    )

    json_path, csv_path = write_benchmark_report(
        report,
        output_dir=tmp_path,
        prefix="benchmark_test",
    )

    assert json_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["config"]["policies"] == ["random"]

    with csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["policy"] == "random"
