# DANTE: Data-Driven Test Case Selection and Prioritization for Long-Running Test Suites
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains the source code and replication package for the research paper, **"DANTE: Data-Driven Test Case Selection and Prioritization for Long-Running Test Suites"** submitted to the 19th IEEE International Conference on Software Testing, Verification and Validation (ICST 2026).

DANTE is a novel Test Case Selection and Prioritization (TCSP) framework designed for large-scale CI/CD pipelines. It leverages a data-driven heuristic that combines probabilistic failure history ("stickiness") and textual relevance to efficiently identify and rank test cases that are most likely to detect faults, matching or exceeding the performance of complex Machine Learning models without the need for training.

## Overview

As software systems grow in complexity, running the entire test suite for every code change becomes a significant bottleneck. DANTE addresses this by combining historical test signals (pass/fail history, stickiness) and the textual similarity between code changes and test artifacts to create a unified "value score" for each test case. This enables intelligent test selection and prioritization, aiming to identify failures more quickly and reduce testing overhead.

DANTE distinguishes itself by being:
1.  **Training-Free**: Unlike ML approaches, it adapts instantly to new data without retraining.
2.  **Adaptive**: It uses a dynamic "recency boost" to prioritize immediate regressions while falling back to relevance for stable components.
3.  **Robust**: It is designed to be resilient to flaky tests and avoids the look-ahead bias common in static learning benchmarks.

This repository provides the code for the entire DANTE ecosystem and, in particular, its main components:
*   **Pipeline Orchestrator (`pipeline_orchestrator.py`)**: Processes raw data from the [Long Running Test Suite (LRTS) dataset](https://dl.acm.org/doi/10.1145/3650212.3680307), reconstructing historical states via Git worktrees to ensure valid retrospective analysis.
*   **Selection Runner (`run_selection.py`)**: Executes test selection experiments under various time budgets, comparing DANTE against heuristics and ML baselines.
*   **Prioritization Runner (`run_prioritization.py`)**: Executes global test prioritization experiments (ordering the full suite), calculating APFDc.
*   **ML Model (`ml_model.py`)**: Implements the Machine Learning baseline (HistGradientBoostingRegressor) used for comparison, supporting Just-In-Time (JIT) training mode.

## Key Features

*   **Probabilistic "Stickiness"**: Models failure persistence using Wilson confidence intervals to weigh historical signals.
*   **Commit-Aware Relevance**: Uses sparse Information Retrieval (TF-IDF) to link code changes to test cases.
*   **Cost-History-Cognizant (CCH)**: Integrates execution cost and failure history into the ranking logic.
*   **Machine Learning Baseline**: Includes a rigorous implementation of a Gradient Boosting Regressor baseline (replicating state-of-the-art approaches) to enable fair comparison.
*   **Look-Ahead Bias Prevention**: The experimentation framework enforces strict chronological ordering (JIT) to prevent data leakage, a critical issue identified in previous benchmarks.

## Experiments

The paper evaluates DANTE in response to three research questions (RQs), supported by specific runner scripts.

#### RQ1: Prioritization Effectiveness
*   **Goal**: To evaluate how well different strategies order the **entire test suite** to find faults as early as possible.
*   **Baselines**: MostFail-CC, LastFail-CCH, QTF, LTR-CCH (Machine Learning).
*   **Runner Script**: `run_prioritization.py`
*   **Key Metric**: **APFDc** (Average Percentage of Faults Detected - cost cognizant).
*   **Output**: JSON solution files and `final_apfdc_results.csv`.

#### RQ2: Test Selection Effectiveness
*   **Goal**: To evaluate the fault detection rate of subsets selected under strict time budgets (e.g., 5%, 10% of total time).
*   **Runner Script**: `run_selection.py`
*   **Key Metrics**:
    *   **%DTC** (Detected Test Cases / Recall).
    *   **SAPFDc** (Selection APFDc - ordering quality within the selected subset).
    *   **SDS** (Structural Diversity Score).
*   **Output**: JSON solution files per build and summary charts in `experiment_results/`.

#### RQ3: Robustness to Flakiness
*   **Goal**: To assess the ability of strategies to prioritize **non-flaky** failures (genuine regressions) over flaky noise.
*   **Analysis**: Performed by analyzing the `%DTC_FLK` metric computed by `run_selection.py` on the experimental results.

## Project Structure
### Core pipeline
- **pipeline_orchestrator.py** – Orchestrates the full data processing pipeline
- **augment_history.py** – Enriches the processed build data with historical context
- **config.py** – Main pipeline configuration  
- **experiment_config.py** – Experiment settings (budgets, paths)

### Models & Strategies
- **ml_model.py** – ML baseline (HistGradientBoostingRegressor)  
- **relevance_strategies.py** – TF-IDF–based relevance strategies  

### Experiment runners
- **run_prioritization.py** – Test Prioritization (RQ1)  
- **run_selection.py** – Test Selection (RQ2, RQ3)
- **post_hoc_prioritizer.py** - Test Selection (SAPFDc)

### Analysis scripts
- **duration_analyzer.py** – Test duration analysis  
- **flakiness_analyzer.py** – Flaky test impact analysis  
- **lookback_analyzer.py** – Historical lookback analysis  
- **developer_behavior_analyzer.py** – Developer behavior patterns  

### Data & utilities
- **lRTS_data_loader.py** – LRTS dataset loader  
- **source_processor.py** – Source code parsing & tokenization  
- **git_utils.py** – Git interaction utilities  
- **cache_utils.py** – Cache management

### Sample Data
The repository includes a small set of pre-processed builds in the `processed_builds/` folder, allowing you to test the framework immediately.  
To process additional builds from the LRTS dataset, run the `pipeline_orchestrator.py` component as described in the [Data Processing Pipeline](#1-data-processing-pipeline-pipeline_orchestratorpy) section.


## Quick Start with Docker

The easiest way to get started with DANTE is using Docker. A video tutorial is available on [YouTube](https://youtu.be/4Q--r07-HAA) that demonstrates the complete installation process.

### Prerequisites
- Docker installed on your system

```bash
    docker-compose run --rm ml_tcsp
```
This will launch an interactive interface that guides you through:

1. Test selection experiments
2. Test prioritization experiments
3. Additional analysis tools

The interface provides clear instructions and options for all DANTE operations, eliminating the need to manually configure paths or run individual scripts.

### What's Included
The Docker container comes pre-configured with:
- All required Python dependencies
- Proper environment setup
- Pre-configured paths for experiments


## Getting Started for Full Installation

### Prerequisites

- Python 3.8+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- Access to the LRTS dataset

---

### Installation

1.  Clone this repository.
2.  Install the required Python packages:
    ```bash
    poetry install
    ```

### Configuration

Before running the pipeline or experiments, you must configure the paths in the following files:

*   **`config.py`**:
    *   `LRTS_RAW_DATA_BASE_PATH`: Set this to the root directory of your LRTS dataset.
    *   `PROJECT_REPOS_CLONE_BASE_PATH`: Specify a directory where project repositories will be cloned.
*   **`experiment_config.py`**:
    *   `LRTS_RAW_DATA_BASE_PATH`: Also set this to your LRTS dataset path.

You can also modify other parameters in these files to customize the pipeline and experiment execution, such as the `TARGET_PROJECT`.

## Running the Pipeline and Experiments

The overall workflow consists of two main stages: data processing (the pipeline) and experiment execution.

### 1. Data Processing Pipeline (`pipeline_orchestrator.py`)

This orchestrator processes the raw data for a target project from the LRTS dataset. For each build, it clones the project repository, checks out the specific commit, tokenizes the code changes and the test files, and calculates the relevance between them.

**To run the pipeline:**
```bash
python pipeline_orchestrator.py
```
This will generate processed JSON files in the OUTPUT_DATA_DIR specified in config.py.
After running the main pipeline, you can augment these files with historical data:

```bash
python augment_history.py
```

### 2. Experiment Execution
The paper evaluates DANTE on three distinct tasks: Test Case Selection, Test Case Prioritization, and Test Case Selection & Prioritization.

**Note on Machine Learning Baselines:**
To run experiments comparing DANTE against the Machine Learning baseline, the system requires specific historical features (history, interaction, context). You have two options:
* **Use Pre-extracted Features:** We provide the pre-computed features used in our study in the `tcp_features/` directory. Ensure the ML_FEATURES_DIR path in experiment_config.py points to this folder.
* **Extract from Scratch:** You can extract fresh features directly from the raw LRTS dataset using the original feature extraction tools provided by Cheng et al (https://dl.acm.org/doi/10.1145/3650212.3680307).
## Test Case Selection (run_selection.py)
This script runs the main selection experiments. It utilizes pre-processed data to construct statistical models, and then runs solvers to select a subset of tests for a set of target builds within a given time budget.
To run the selection experiments:
```bash
python run_selection.py
```
## Test Case Prioritization (run_prioritization.py)
This script runs the prioritization experiments. It uses the same statistical models to score every test case in a build and then orders the entire suite to find failures as early as possible.
To run the prioritization experiments:
```bash
python run_prioritization.py
```
Both runners will create a new timestamped directory in the RESULTS_DIR containing the detailed results of the experiment, including solution files for each build and summary charts.

## Test Case Selection & Prioritization (post_hoc_analyzer.py)
This script performs a post-hoc ordering on the output of test selection experiments (so it must be run **after** run_selection.py on a specific project). 
For each selected subset from a run, it applies various prioritization heuristics (e.g., density-based) and evaluates the resulting test order using the NAPFDc metric.
To run the selection & prioritization experiments:
```bash
python run_selection.py
python post_hoc_analyzer.py
```

## 3. Additional Analysis Scripts
This repository includes several scripts for in-depth analysis:

- **developer_behavior_analyzer.py:** Analyzes test failure history to infer developer patterns.

- **duration_analyzer.py:** Compares the duration of failing tests versus all tests.

- **flakiness_analyzer.py:** Investigates how different strategies are affected by flaky tests.

- **lookback_analyzer.py:** Helps in determining the optimal lookback window for historical analysis.

Each of these scripts can be run from the command line and may require specific arguments. Please refer to the argparse section within each file for usage details.

