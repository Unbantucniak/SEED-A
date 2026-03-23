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
