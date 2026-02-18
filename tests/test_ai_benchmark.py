"""Tests for AI benchmark reporting utilities."""

from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from swos420.ai.benchmark import (
    BenchmarkError,
    _build_policy_agent,
    decode_flat_action,
    flatten_observation,
    run_benchmark,
    write_benchmark_report,
)


class TestFlattenObservation:
    def test_concatenates_and_flattens(self):
        obs = {
            "league_table": np.ones((4, 6), dtype=np.float32),
            "own_squad": np.ones((16, 12), dtype=np.float32),
            "finances": np.ones(4, dtype=np.float32),
            "meta": np.ones(4, dtype=np.float32),
        }
        flat = flatten_observation(obs)
        expected_len = 4 * 6 + 16 * 12 + 4 + 4
        assert flat.shape == (expected_len,)
        assert flat.dtype == np.float32
        assert np.all(flat == 1.0)


class TestDecodeFlatAction:
    def test_rejects_wrong_shape(self):
        with pytest.raises(BenchmarkError, match="Expected 13 action components"):
            decode_flat_action([0, 1, 2])

    def test_valid_13_action(self):
        raw = list(range(13))
        result = decode_flat_action(raw)
        assert result["formation"] == 0
        assert result["style"] == 1
        assert result["training_focus"] == 2
        assert result["scouting_level"] == 3
        assert result["transfer_bid_0"] == 4
        assert result["sub_2"] == 12

    def test_bid_amounts_normalized(self):
        """Bid amounts should be divided by 9.0."""
        raw = [0] * 13
        raw[5] = 9  # bid_amount_0
        result = decode_flat_action(raw)
        assert abs(float(result["bid_amount_0"]) - 1.0) < 1e-6


class TestBuildPolicyAgent:
    def test_random_agent(self):
        from swos420.ai.env import SWOSManagerEnv
        env = SWOSManagerEnv(num_teams=4, seed=42)
        env.reset()
        agent = _build_policy_agent("random", env.action_space("club_0"), 42, None, True)
        assert agent is not None

    def test_heuristic_agent(self):
        from swos420.ai.env import SWOSManagerEnv
        env = SWOSManagerEnv(num_teams=4, seed=42)
        env.reset()
        agent = _build_policy_agent("heuristic", env.action_space("club_0"), 42, None, True)
        assert agent is not None

    def test_ppo_no_model_path_raises(self):
        with pytest.raises(BenchmarkError, match="requires --model-path"):
            _build_policy_agent("ppo", None, 42, None, True)

    def test_unknown_policy_raises(self):
        with pytest.raises(BenchmarkError, match="Unsupported policy"):
            _build_policy_agent("magic", None, 42, None, True)


class TestRunBenchmarkValidation:
    def test_seasons_less_than_1_raises(self):
        with pytest.raises(BenchmarkError, match="seasons must be >= 1"):
            run_benchmark(policies=["random"], seasons=0, num_teams=4, seed=42)

    def test_num_teams_less_than_2_raises(self):
        with pytest.raises(BenchmarkError, match="num_teams must be >= 2"):
            run_benchmark(policies=["random"], seasons=1, num_teams=1, seed=42)

    def test_unknown_policy_raises(self):
        with pytest.raises(BenchmarkError, match="Unknown policy values"):
            run_benchmark(policies=["magic"], seasons=1, num_teams=4, seed=42)


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

