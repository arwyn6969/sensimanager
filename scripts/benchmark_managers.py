#!/usr/bin/env python3
"""Benchmark SWOS manager policies over multiple seasons.

Examples:
    python scripts/benchmark_managers.py --seasons 10 --num-teams 8
    python scripts/benchmark_managers.py --policies random heuristic ppo --model-path models/swos420_ppo
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from swos420.ai.benchmark import (  # noqa: E402
    BenchmarkError,
    run_benchmark,
    write_benchmark_report,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_managers")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SWOS420 benchmark runner for random/heuristic/PPO manager policies"
    )
    parser.add_argument(
        "--policies",
        nargs="+",
        default=["random", "heuristic"],
        help="Policy names to benchmark (random, heuristic, ppo)",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        default=10,
        help="Number of seasons per policy (default: 10)",
    )
    parser.add_argument(
        "--num-teams",
        type=int,
        default=4,
        help="Number of teams in each benchmark league (default: 4)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed (default: 42)",
    )
    parser.add_argument(
        "--model-path",
        default="models/swos420_ppo",
        help="Path to PPO model (used when policies includes 'ppo')",
    )
    parser.add_argument(
        "--stochastic-model",
        action="store_true",
        help="Use stochastic PPO actions (default is deterministic)",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/benchmarks",
        help="Directory to write JSON/CSV benchmark reports",
    )
    parser.add_argument(
        "--output-prefix",
        default="manager_benchmark",
        help="Report filename prefix",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    model_path = Path(args.model_path) if "ppo" in {p.lower() for p in args.policies} else None

    try:
        report = run_benchmark(
            policies=args.policies,
            seasons=args.seasons,
            num_teams=args.num_teams,
            seed=args.seed,
            model_path=model_path,
            deterministic_model=not args.stochastic_model,
        )
        json_path, csv_path = write_benchmark_report(
            report,
            output_dir=Path(args.output_dir),
            prefix=args.output_prefix,
        )
    except BenchmarkError as exc:
        logger.error(str(exc))
        return 2

    logger.info("Benchmark complete")
    logger.info("JSON report: %s", json_path)
    logger.info("CSV report: %s", csv_path)

    for policy, payload in report["results"].items():
        summary = payload["summary"]
        logger.info(
            "%-9s mean_reward=%+0.3f std=%0.3f champions=%s",
            policy,
            summary["mean_reward"],
            summary["reward_std"],
            summary["champion_distribution"],
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
