# SEED-A

Self-Evolving Experience-Driven Agents

SEED-A is a research-oriented engineering project for building long-running software agents that can accumulate, evaluate, route, and evolve experience over time.

## Overview

Modern LLM-based software agents often suffer from:
- forgetting previously successful solutions,
- low experience reuse efficiency,
- stale or conflicting knowledge in long-running tasks.

SEED-A addresses these issues with a complete experience lifecycle:
1. experience representation and graph construction,
2. experience ingestion, scoring, routing, and evolution,
3. prototype integration and benchmark-driven evaluation.

## Core Capabilities

- Experience Unit schema for task intent, context state, operation sequence, constraints, and execution result.
- Experience Graph with typed edges and searchable metadata.
- Dynamic metadata updates (success rate, timeliness, usage, conflict score).
- Strategy routing across:
  - RAG retrieval,
  - template reuse,
  - prompt engineering,
  - fine-tuning path.
- Enhanced modules for:
  - LLM-as-Judge quality scoring,
  - adversarial validation,
  - online reinforcement-style routing optimization.
- Experiment framework with baselines and automated reporting.

## Repository Structure

```text
.
├── src/
│   ├── common/                 # shared config loader
│   ├── experience_graph/       # graph model and operations
│   ├── experience_manager/     # lifecycle management
│   ├── routing_engine/         # strategy routing and optimization
│   ├── monitoring/             # health, logging, metrics
│   └── prototype/              # VS Code prototype (backend + extension)
├── experiments/
│   ├── baselines/              # baseline implementations
│   ├── benchmarks/             # task datasets
│   ├── run_experiment.py       # experiment entry
│   ├── experiment_runner.py    # runner and report generator
│   └── experiment_params.template.toml
├── tests/
├── tools/
├── config.toml
├── requirements.txt
└── demo.py
```

## Quick Start

### 1) Install dependencies

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
# source venv/bin/activate

pip install -r requirements.txt
```

### 2) Run demo

```bash
python demo.py
```

### 3) Run tests

```bash
python -m unittest discover -s tests -v
# or
python -m pytest tests/ -v
```

### 4) Run experiments

```bash
cd experiments
python run_experiment.py --rounds 3 --seed 42
```

Use external dataset:

```bash
python run_experiment.py --dataset-json ./benchmarks/expanded_tasks.json --rounds 3 --seed 42
```

Enable simulated latency for baseline behavior studies:

```bash
python run_experiment.py --rounds 1 --simulate-latency
```

When `--rounds > 1`, the generated report includes stability metrics (mean success rate, standard deviation, and 95% confidence interval across rounds).

### 5) Run G1 (100+ tasks, fixed params)

```bash
cd experiments
py run_g1_experiment.py --rebuild-dataset
```

This command will:
- build a fixed `120`-task dataset at `experiments/benchmarks/g1_full_120_tasks.json`,
- run the baseline comparison with frozen parameters,
- write outputs to `results/`.

Reference config file:
- `experiments/experiment_params.g1.toml`

### 6) Run G2 (multi-seed significance + effect size)

```bash
cd experiments
py run_g2_analysis.py --seeds 11,22,33,44,55 --rounds 1
```

This command will:
- run all baselines across multiple random seeds on the fixed dataset,
- compute Mann-Whitney U significance and Cliff's delta effect sizes,
- export `g2_stats_*.json` and `g2_stats_*_report.md` under `results/`.

### 7) Run G3 (routing ablation)

```bash
cd experiments
py run_g3_ablation.py --seeds 11,22,33 --rounds 1
```

This command will:
- run route ablation scenarios (strategy disable + weight variants),
- compare `ours_proposed_scheme` metrics across scenarios,
- export `g3_ablation_*.json` and `g3_ablation_*_report.md` under `results/`.

### 8) Experiment Process Log (new)

All experiment entries now append a process/result record to `experiment_run_log.md` in the corresponding output directory.

Included scripts:
- `experiments/run_experiment.py`
- `experiments/run_g1_experiment.py`
- `experiments/run_g2_analysis.py`
- `experiments/run_g3_ablation.py`

Each record includes:
- run timestamp and title,
- full parameters,
- output files and key result pointers.

Output path notes:
- For `run_g3_ablation.py`, default paths remain script-relative for backward compatibility.
- If you pass custom relative paths (for example `--output-dir experiments/results` from repo root), they are resolved against the current working directory.

## Configuration

SEED-A uses `config.toml` as the single configuration entry.

Main sections:
- `experience_graph`
- `experience_manager`
- `routing_engine`
- `llm`
- `redis`
- `experiment`
- `logging`

## Experiment Template

Recommended experiment parameter template:

- `experiments/experiment_params.template.toml`

Example reproducible run:

```bash
cd experiments
python run_experiment.py --rounds 5 --seed 42 --dataset-json ./benchmarks/expanded_tasks.json --output-dir ../results
```

## Tech Stack

- Python (core system, experiments, APIs)
- TypeScript (VS Code extension prototype)
- Pydantic, NumPy, scikit-learn, FastAPI, matplotlib

## Development Notes

- Generated artifacts (for example `results/`, `models/`, caches) are excluded by `.gitignore`.
- Some local project documents are intentionally excluded from version control.

## License

MIT License
