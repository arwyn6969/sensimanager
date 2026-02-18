# SWOS420 AI Training Strategy and Difficulty Guide

Date: 2026-02-18
Status: Active

## 1. Purpose

This document defines a reproducible training and evaluation flow for SWOS420 manager policies.
It is designed to keep model progress measurable while the engine/port work continues in parallel.

## 2. Core Constraints

- Multi-agent environment with shared policy and delayed rewards.
- Tactical actions combine discrete and continuous-like components (via discretized bid amounts).
- Long horizon signal: one episode is a full season.
- Non-stationary opponents when self-play is enabled.

## 3. Difficulty Ladder

Use a staged curriculum to avoid unstable early learning.

1. `Level 0` (stability): 4 teams, short PPO runs, deterministic evaluation.
2. `Level 1` (pressure): 8 teams, same reward weights, higher timestep budget.
3. `Level 2` (robustness): randomized seeds + mixed baseline opponents.
4. `Level 3` (scale): 16+ teams and longer training windows.

Promotion rule: only move up after reward and standings metrics are stable for at least 3 benchmark runs.

## 4. Standard Workflow

### Train

```bash
python scripts/train_managers.py --timesteps 500000 --num-teams 8 --device auto --model-path models/swos420_ppo
```

### Evaluate quick sanity

```bash
python scripts/train_managers.py --eval-only --num-teams 8 --model-path models/swos420_ppo
```

### Benchmark policies (machine-readable output)

```bash
python scripts/benchmark_managers.py \
  --policies random heuristic ppo \
  --seasons 10 \
  --num-teams 8 \
  --seed 42 \
  --model-path models/swos420_ppo \
  --output-dir reports/benchmarks
```

Output artifacts:
- JSON report: per-policy summaries + per-season details.
- CSV report: flat table for dashboarding and trend diffs.

## 5. Metrics to Track

Primary:
- Mean season reward per policy.
- Reward standard deviation across seasons.
- Champion distribution (how concentrated wins are).
- Mean champion points.

Secondary:
- Matchday count stability.
- Min/max reward spread across clubs.

## 6. Recommended Acceptance Gates

1. PPO must beat `heuristic` mean reward over 10 seasons with same seeds.
2. PPO reward std should not increase by more than 20% versus prior accepted run.
3. Champion distribution should show diversity at 8+ teams (not always one club).

## 7. Iteration Knobs

When training stalls, adjust in this order:

1. Reward shaping weights in `src/swos420/ai/rewards.py`.
2. PPO hyperparameters in `scripts/train_managers.py` (`n_steps`, `batch_size`, `ent_coef`, learning rate).
3. Observation richness in `src/swos420/ai/obs.py`.

Only change one knob family per experiment block to keep attribution clear.

## 8. Experiment Logging Template

For each run, record:
- Git commit hash.
- Command used.
- Model path.
- Benchmark JSON/CSV paths.
- Pass/fail against acceptance gates.

This keeps comparisons valid across concurrent engineering tracks.
