# Estimation Assistant — Multi-Agent Framework (Python, Groq API)

A self-contained, runnable Python **multi-agent framework** that performs
LLM-based Agile effort estimation through **five cooperating agents** that
communicate via explicit, logged JSON messages — addressing two specific
gaps identified in the reference paper. The original four-agent pipeline
(synthetic data, hours) is unchanged; a fifth **Learning Agent** plus a real
public dataset path (NeoDataset, story points) extend it side by side.

## Quick Start

1. **Unzip** the folder.
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # macOS/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Create your `.env` with a free Groq API key (see `.env.example`):
   ```
   cp .env.example .env           # then edit .env and paste your key
   ```
   Get a free key at <https://console.groq.com/keys>. No key is bundled.
5. Run the full demo (four-agent pipeline on the 8 synthetic stories):
   ```
   python -m estimation_assistant demo
   ```
6. Open `output/comparison_report.md` and `output/agent_messages.log` to see
   the results and the agent-to-agent message trail.
7. (Optional, real data) Run the pipeline on the real NeoDataset sample —
   works **offline**, the sample is shipped in `data/`:
   ```
   python -m estimation_assistant run-neodataset
   python -m estimation_assistant learn-over-time --runs 5
   ```
   See "Running on the real NeoDataset" below.
8. (Optional, experiments) Run the held-out ablation experiment and inspect
   the results — see "Running the experiments" below:
   ```
   python -m estimation_assistant experiment --selftest   # offline plumbing check
   python -m estimation_assistant experiment              # real run (needs a key)
   ```

> **Reminder:** this compressed folder is the full deliverable — no additional
> setup beyond the Quick Start steps should be necessary. No internet access
> is needed at grading time: the NeoDataset sample (`data/user_stories/
> neodataset_sample.json` + `data/actuals_neodataset.json`) is committed, so
> `run-neodataset` and `learn-over-time` work fully offline. The one-time
> sampler `python scripts/generate_sample.py` (needs internet) only has to be
> re-run if you want to re-draw the sample.

## Other CLI commands

```bash
python -m estimation_assistant estimate data/user_stories/us1.json
python -m estimation_assistant record-actual us1 5.5
python -m estimation_assistant evaluate
python -m estimation_assistant demo
python -m estimation_assistant run-neodataset
python -m estimation_assistant learn-over-time --runs 5
python -m estimation_assistant report [--neodataset]
python -m estimation_assistant experiment [--selftest] [--models ...] [--configs ...]
python -m estimation_assistant reset-state
```

## GUI

A simple Tkinter GUI (`gui.py`) is available at the repo root to run the CLI commands without typing in the terminal.

### Launch
```bash
# from the project root with virtualenv active
python gui.py
# or on Windows PowerShell
.\venv\Scripts\python.exe gui.py
```

### Features
- **Estimate…** – select a user story JSON from `data/user_stories/` and run `estimate`.
- **Record Actual…** – enter `story_id` and `hours` to run `record-actual`.
- **Evaluate** – run `evaluate`.
- **Run Demo** – run `demo`.
- **Run NeoDataset** – run `run-neodataset`.
- **Learn Over Time…** – choose number of runs (default 5) to run `learn-over-time`.
- **Generate Report** – run `report`; optionally include NeoDataset (`--neodataset`).
- **Open Outputs** – open the `output/` folder.
- **Console** tab shows live streaming logs; **Comparison Report**, **NeoDataset Report**, **Agent Messages** tabs show viewer files refreshed on completion.
- Buttons are disabled while a command runs; status bar shows command, exit code, and elapsed time.


## The problem: two gaps from the reference paper

**Reference:** Pavlič, L., Saklamaeva, V., & Beranič, T. (2024).
"Can Large-Language Models Replace Humans in Agile Effort Estimation? Lessons
from a Controlled Experiment." *Applied Sciences*, 14(24), 12006.
https://doi.org/10.3390/app142412006

```
Estimation Accuracy(UserStory) = Actual_Effort(UserStory) / Estimated_Effort(UserStory) × 100%
```

**Results:** LLM (experimental) group **16% average accuracy** (SD 9.2%);
human/conventional (control) group **60% average accuracy** (SD 24.5%).

 *Gap 1* — the tool estimated effort with no knowledge of developer
experience or code familiarity, making estimates unrealistic. *Gap 2* — there
was no mechanism to learn from past errors; future estimates were never
adjusted based on actual outcomes.

## Related Work — why this is an original contribution

There is a related paper, **Bui, Thanh-Long et al. (2025), "SEEAgent: An
LLM-based multi-agent framework for agile effort estimation"**
(arXiv:2509.14483), which also proposes a multi-agent LLM framework for
effort estimation. SEEAgent's agents coordinate and discuss with each other
and with human developers to reach a *consensus* estimate; it does **not**
implement automatic historical calibration or explicit
developer-experience-aware prompting as first-class agents.

** original contribution** is specifically:

1. A dedicated **Calibration Agent** that automatically learns a correction
   ratio from historical (estimated vs. actual) records per developer/team and
   applies it without any manual recalibration step — this directly implements
   the "future work" the original Pavlič et al. paper flagged but never built,
   and is not what SEEAgent does (SEEAgent uses consensus/discussion, not
   historical-accuracy-based self-correction).
2. A dedicated **Developer Context Agent** that structurally separates and
   injects developer experience/familiarity into the estimation pipeline as
   its own agent responsibility, rather than folding it into a general
   discussion/consensus mechanism.

## The five agents
 (the fifth agent is new in
the NeoDataset addendum; the original four are untouched):

| # | Agent | Module | Message in → out |
|---|-------|--------|------------------|
| 1 | **Developer Context Agent** (Gap 1) | `developer_context_agent.py` | `UserStory` → `DeveloperContextMessage` |
| 2 | **Estimation Agent** | `estimation_agent.py` | `DeveloperContextMessage` → `EstimationMessage` |
| 3 | **Calibration Agent** (Gap 2) | `calibration_agent.py` | `EstimationMessage` → `CalibrationMessage` |
| 4 | **Evaluation Agent** | `evaluation_agent.py` | stored estimate + actual → `EvaluationMessage` |
| 5 | **Learning Agent** (cross-run, NEW) | `learning_agent.py` | `list[EvaluationMessage]` → `LearningUpdateMessage` |

- **Developer Context Agent** — receives a user story + developer/team ID,
  looks up that developer's experience level and code familiarity
  (`data/developer_profiles.json`), and produces a context-enriched request.
  No external/manual prompt is required from the end user.
- **Estimation Agent** — builds the LLM prompt from
  `estimation_assistant/prompts/estimate.txt` (the only place a prompt is
  constructed), calls the Groq LLM, and parses the reply line-by-line as
  `TASK: <name> | HOURS: <number> | RATIONALE: <text>`.
- **Calibration Agent** — computes a correction ratio (mean of
  `actual/estimated` from ≥2 records for that developer/team; else the global
  mean across all records; else `1.0`), applies it to each task, and learns
  over time via `record-actual` with zero manual recalibration.
- **Evaluation Agent** — once actual effort is recorded, compares calibrated
  (and raw) estimates against actual effort using the paper's exact formula
  and compares against the paper's baseline numbers (16%/60%).

```
[DeveloperContextAgent -> EstimationAgent] (send) user_story_id=us1
[LearningAgent -> CalibrationAgent] (send) user_story_id=?
```

`orchestrator.py` owns the pipeline: `run_estimation_pipeline(user_story) ->
CalibrationMessage`, calling the agents in sequence and writing
`output/estimate_<id>.json` (including which agent produced what). After a
full NeoDataset run, the Learning Agent's `update()` is called once with all
of that run's `EvaluationMessage`s.


## Data flow / commands

- `estimate <file.json>` — runs Developer Context → Estimation → Calibration
  and writes `output/estimate_<id>.json` (+ index).
- `record-actual <id> <hours>` — appends a `CalibrationRecord` to
  `data/calibration_history.json` and updates `data/actuals.json`: this is the
  agent "learning" from real outcomes.
- `evaluate` — evaluates every story that has both an estimate and an actual,
  writes `output/comparison_report.md`, prints summary vs. the paper baselines.
- `demo` — runs the full pipeline on all 8 sample stories, automatically
  records their actuals from `data/actuals.json` (no manual `record-actual`
  needed), then runs `evaluate_all()` and writes the comparison report.
  For reproducibility, `demo` does **not** append new entries to
  `data/calibration_history.json` (repeat runs stay identical); use
  `record-actual` manually to see the Calibration Agent learn live.

Evaluation reads actual hours from `data/actuals.json` (the simpler of the two
options in the spec; `record-actual` writes there too).

## Running on the real NeoDataset

**Dataset citation:** Neo, G. S. et al. (2024). *User Story NeoDataset*
(20,479 user stories mined from 33 open-source GitLab projects, each with
real text and a real recorded Story Points value — GitLab's "Weight" field).
Mendeley Data: https://doi.org/10.17632/skk2wn9j86 (HuggingFace mirror
`giseldo/neodataset`, file `issues.csv`).

```
python scripts/generate_sample.py          # one-time, needs internet (sample already committed)
python -m estimation_assistant run-neodataset
python -m estimation_assistant learn-over-time --runs 5
python -m estimation_assistant report --neodataset
```

## Running the experiments

Beyond the demo, the project ships a **held-out ablation experiment** that
turns the agent pipeline into a controlled, reproducible comparison. It is
built to be honest first: every number it reports comes from a real LLM reply,
nothing is fabricated, smoothed, or hardcoded, and the settings are fixed
*before* any result is seen (`config.yaml`, `experiment:` block).

```
python -m estimation_assistant experiment --selftest   # offline plumbing check
python -m estimation_assistant experiment              # real run (needs a Groq key)
python -m estimation_assistant experiment --models openai/gpt-oss-20b --rounds 3
python -m estimation_assistant experiment --configs issue_context,issue_context_calibrated
python -m estimation_assistant reset-state             # restore pristine runtime state
```

### Models compared

Each run compares three Groq models, taken from `config.yaml` (`models:`) or
overridden with `--models id1,id2,...`:

| Model id | Notes |
|---|---|
| `openai/gpt-oss-20b` | small, fastest of the three |
| `openai/gpt-oss-120b` | large, usually the most accurate |
| `qwen/qwen3.8-27b` | general reasoning model |

```
python -c "from groq import Groq; import os; from dotenv import load_dotenv; load_dotenv(); \
print('\n'.join(sorted(m.id for m in Groq(api_key=os.environ['GROQ_API_KEY']).models.list().data)))"
```

and pass any subset with `--models`. A model the key cannot use is reported as
`404` → every story falls back, which is visible in the `fallbk` column rather
than being silently hidden.

### What it compares (stepwise / forward-nested ablation)

The four configs each add exactly one factor over the previous, so each
adjacent paired comparison isolates that factor:

| # | Config | Granularity | Developer context | Calibration |
|---|--------|-------------|-------------------|-------------|
| 1 | `task_no_context` | task decomposition | no | no |
| 2 | `issue_no_context` | whole issue | no | no |
| 3 | `issue_context` | whole issue | yes (Gap 1) | no |
| 4 | `issue_context_calibrated` | whole issue | yes | yes (Gap 2) |

The reported comparisons are: **granularity** (1→2), **developer context**
(2→3), **calibration** (3→4), and **full pipeline vs baseline** (1→4). This is
a *stepwise*, not a full-factorial, design — documented here and in every
`summary.md` so it cannot be mistaken for a factorial decomposition.

### Held-out protocol (no leakage)

- Stories are split **per project** (stratified), seed 42,
  `n_train = max(1, round(0.6 × n_project))`, capped so at least one test
  story remains when a project has more than one. On the committed 40-story
  sample that is **24 train / 16 test**.
- Calibration ratios are learned from the **training split only** and applied
  to the test split. Nothing from the test split ever influences a prediction.
- A failed reply (unparseable for every round) is a **fallback**: its
  prediction is left `None`, it is excluded from the metrics (never imputed),
  and it is counted in the `fallback` column and per-story CSV.

### Outputs

Written to `output/experiment/`:

| File | Contents |
|---|---|
| `results.json` | full structured result (settings, per-config metrics, comparisons, per-story records) |
| `results.csv` | one row per model × config (final + raw metrics, CI, ratios) |
| `per_story.csv` | one row per model × config × split × story (actual, raw/final prediction, fallback) |
| `summary.md` | human-readable tables and how-to-read notes |
| `config_used.json` | the exact effective settings for the run |
| `cache.json` | reply cache keyed by `sha256(model, round nonce, system, user)` |

`cache.json` is written **every 10 stories as well as at the end**, so a long
live run that is interrupted — a dropped connection, a hard `Ctrl-C`, a rate
limit that outlasts the retry budget — keeps every reply it already paid for.
Re-running the identical command resumes from cache, making no network call for
a reply it already has, so an experiment can be finished across several
sessions without re-paying for the first half.

`--selftest` swaps the LLM for a deterministic offline stub and writes to
`output/experiment_selftest/` instead; **every** file there is stamped
`SELFTEST - NOT RESULTS` and it exists only to prove the plumbing works.

### `generate_sample.py` defaults

`python scripts/generate_sample.py` (needs internet) re-draws the committed
sample. Its defaults — `--n-projects 8`, `--stories-per-project 5`,
`--seed 42` — reproduce exactly the shipped `neodataset_sample.json`, so a
no-argument run does not silently change the dataset a comparison was built
on. The experiment accepts the same `--projects` / `--stories-per-project` /
`--seed` subsetting to shrink a live run during development.


### Acceptance checklist

`EXPERIMENT_CHECKLIST.md` is the acceptance checklist for the experiment spec:
every requirement area is marked implemented with the code and the offline test
that proves it, and the proof is a single `.venv/bin/python -m pytest -q` run
(**145 passed**). It is documentation of the machinery, not of any result — no
numbers appear there until a live run is executed.


## Project layout

```
estimation_assistant/
├── requirements.txt
├── .env.example
├── README.md
├── EXPERIMENT_CHECKLIST.md         # acceptance checklist for the experiment spec
├── config.yaml                     # LLM settings + fixed experiment settings
├── workflow_diagram.png/.svg/.mmd  # five-agent workflow diagram + source
├── scripts/
│   ├── generate_sample.py          # NeoDataset sampler (parameterised; needs internet)
│   ├── generate_diagram.py         # regenerates the workflow diagram
│   └── make_delivery_zip.py        # builds the deliverable ZIP (refuses to ship a real key)
├── data/
│   ├── user_stories/               # 8 synthetic stories + neodataset_sample.json (40 real)
│   ├── developer_profiles.json     # synthetic teams + project-as-team proxies
│   ├── calibration_history.json    # shared by both paths; Learning Agent appends (+ .bak)
│   ├── learning_state.json         # cross-run EWMA ratios + run accuracies (created on first learn run)
│   ├── actuals.json                # synthetic actuals (hours)
│   └── actuals_neodataset.json     # real story-point actuals (committed, offline)
├── output/                         # generated at runtime (gitignored)
├── estimation_assistant/
│   ├── __init__.py
│   ├── __main__.py                 # CLI (estimate / record-actual / evaluate / demo / run-neodataset /
│   │                               #      learn-over-time / report / experiment / reset-state)
│   ├── llm_client.py               # LlmClient + GroqLlmClient + FakeLlmClient; task & issue reply parsers
│   ├── models.py                   # UserStory, TaskEstimate, DeveloperProfile, ...
│   ├── messages.py                 # the five message dataclasses (+ LearningUpdateMessage, fallback flags)
│   ├── developer_context_agent.py
│   ├── estimation_agent.py         # unit="hours"|"storypoints" prompt selection; fallback bookkeeping
│   ├── calibration_agent.py        # unchanged — picks up Learning Agent ratios as-is
│   ├── evaluation_agent.py         # unit-aware labels + conditional "D. Cross-Run Learning" subsection
│   ├── learning_agent.py           # NEW: cross-run EWMA refinement (alpha=0.3)
│   ├── experiment.py               # NEW: held-out ablation harness (split, rounds, cache, comparison)
│   ├── metrics.py                  # NEW: stdlib-only metrics + bootstrap CIs (no numpy/scipy)
│   ├── orchestrator.py
│   ├── report_generator.py         # Word report (report.docx), conditional D subsection
│   ├── utils.py                    # paths + message logging
│   └── prompts/
│       ├── estimate.txt            # hours prompt (synthetic path, unchanged)
│       ├── estimate_storypoints.txt# Fibonacci story-points prompt (NeoDataset path)
│       ├── experiment_task_no_context.txt
│       ├── experiment_task_context.txt
│       ├── experiment_issue_no_context.txt
│       └── experiment_issue_context.txt
└── tests/                          # pytest, no network / no API key
    ├── test_experiment.py          # NEW: split / calibration / metrics / cache / CLI, fully offline
    └── test_metrics.py             # NEW: hand-computed metric + bootstrap tests



