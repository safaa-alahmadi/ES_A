# Experiment Framework — Acceptance Checklist

This document is the acceptance checklist for the estimation-**experiment**
specification. Every requirement area from the spec is listed with the concrete
evidence that it is implemented, and the offline test that proves it. Nothing
here asserts a *result*; it asserts that the machinery is correct, honest, and
reproducible. Real numbers only appear when a live run is executed.

Legend: `[x]` implemented and covered by a test · `[~]` implemented, verified
manually (no automated assertion) · `[!]` deliberately not applicable, with a
reason.

Run the proof for every `[x]` at once:

```bash
.venv/bin/python -m pytest -q          # 145 passed
```

The two suites that carry the experiment coverage are
`tests/test_metrics.py` (metrics + bootstrap) and `tests/test_experiment.py`
(split / calibration / runner / cache / CLI). The rewritten
`tests/test_llm_client.py` covers the reply parsers, including the new
`parse_issue_reply`.

---

## 1. Metrics module (`estimation_assistant/metrics.py`)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1.1 | Metrics computed with the **standard library only** (no numpy/scipy/pandas) | `[x]` | `metrics.py` imports only `csv`, `math`, `random`, `statistics`, `typing`. Same for `experiment.py`. |
| 1.2 | Point metrics: MAE, RMSE, MdAE, ME, SA, plus relative metrics MAPE, MdAPE, WAPE | `[x]` | `error_metrics()` → keys `MAE RMSE MdAE ME SA MAPE MdAPE WAPE n`; `tests/test_metrics.py::TestErrorMetrics::test_hand_computed_values`. |
| 1.3 | A perfect prediction yields zero error | `[x]` | `TestErrorMetrics::test_perfect_predictions`. |
| 1.4 | Symmetric-accuracy tolerance is 1 (±1) for actual ≤ 2, else 2 (±2) | `[x]` | `error_metrics` `sa_tol`; `TestErrorMetrics::test_sa_counts_only_within_tolerance`. |
| 1.5 | Length mismatch is a hard error, not silent truncation | `[x]` | `error_metrics` raises `ValueError`; `test_length_mismatch_raises`. |
| 1.6 | Empty series returns `NaN` metrics with `n=0` (never a fabricated 0) | `[x]` | `TestErrorMetrics::test_empty_series_returns_nan_metrics`. |
| 1.7 | Zero-actual stories are dropped from MAPE (no divide-by-zero) but kept for absolute error | `[x]` | `TestErrorMetrics::test_zero_actual_series_is_dropped_from_mape`. |
| 1.8 | Ratio aggregate supports `median` (default) and `mean`; unknown stat raises | `[x]` | `aggregate_ratios()`; `TestAggregateRatios` (median/mean/unknown/mismatch/empty). |
| 1.9 | Ratio summary reports median/mean ratio, log2 MAE, and over/under counts | `[x]` | `ratio_summary()`; `TestRatioSummary` (hand-computed, under-counted, empty). |
| 1.10 | Percentile bootstrap CI, **seeded** so it is reproducible | `[x]` | `bootstrap_ci()`; `TestBootstrapCi::{test_reproducible_with_same_seed, test_ci_brackets_point_statistic, test_constant_series_gives_degenerate_ci}`. |
| 1.11 | Paired bootstrap CI on a difference, resampling the **same indices** in both arms | `[x]` | `paired_bootstrap_diff_ci()`; `TestPairedBootstrapDiffCi::{test_clear_difference_sign, test_identical_series_zero_diff, test_length_mismatch_raises, test_reproducible}`. |
| 1.12 | Per-agent aggregation helper (raw vs calibrated, task counts) | `[x]` | `agent_metrics()`; `TestAgentMetrics` (raw+calibrated, missing-calibrated omitted, ratio = predicted/actual). |
| 1.13 | CSV writer with stable/inferred column order | `[x]` | `write_csv()`; `TestWriteCsv::{test_writes_header_and_rows, test_infers_fieldnames_when_omitted}`. |

## 2. Fallback handling (failed / unparseable LLM replies)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 2.1 | A reply that fails to parse is a **fallback**, never a fabricated value | `[x]` | `_predict_story()` sets `is_fallback=True`, `predicted_raw=None`. |
| 2.2 | Fallbacks are **excluded** from every metric (never imputed) | `[x]` | `_aligned()` skips `None`; `TestConfigMetrics::test_fallback_excluded_and_counted`. |
| 2.3 | Fallbacks are **counted** and reported as a rate | `[x]` | `_fallback_rate()`; same test asserts the exclusion and the count together. |
| 2.4 | Fallback reason is recorded per story (first error, or `no_rounds`) | `[x]` | `_predict_story()` `fallback_reason`; surfaced in `per_story.csv`. |
| 2.5 | A partial failure across rounds does **not** discard the story — the mean over valid rounds is used | `[x]` | `_predict_story()` `partial_round_failure`; `round_estimates`/`round_failures` retained. |
| 2.6 | Network/parse exceptions are recorded per call, never abort the whole run | `[x]` | `_call_llm()` catches `Exception` → `(reply, error)`. |
| 2.7 | The agent path distinguishes fallbacks from real replies on the message itself | `[x]` | `messages.EstimationMessage.is_fallback`/`fallback_reason`, set in `estimation_agent.py`; `tests/test_estimation_agent.py`. |

## 3. Issue vs task granularity

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 3.1 | **Task** granularity asks for `TASK: ... | POINTS: ... | RATIONALE: ...` lines, summed | `[x]` | `parse_estimate()` uses `parse_llm_reply`; `TestParseEstimate::test_task_granularity_sums_points`. |
| 3.2 | **Issue** granularity asks for one `ESTIMATE: <n> | RATIONALE: ...` line | `[x]` | `parse_estimate()` uses `parse_issue_reply`; `TestParseEstimate::test_issue_granularity_reads_estimate`. |
| 3.3 | A new issue-reply parser is a first-class client function | `[x]` | `llm_client.parse_issue_reply()`; `tests/test_llm_client.py::TestParseIssueReply` (plain, aliases, prose, fenced, non-positive, optional rationale, decimal). |
| 3.4 | Each granularity has its own prompt template | `[x]` | `PROMPT_FILES`; `prompts/experiment_{task,issue}_{no_context,context}.txt`. |
| 3.5 | Unparseable reply → `None` (feeds §2, not a zero) | `[x]` | `TestParseEstimate::test_unparseable_returns_none`. |

## 4. Four ablation configs (stepwise / forward-nested)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 4.1 | Exactly four configs: `task_no_context`, `issue_no_context`, `issue_context`, `issue_context_calibrated` | `[x]` | `DEFAULT_CONFIGS`. |
| 4.2 | They are **forward-nested** — each step adds one factor | `[x]` | `DEFAULT_CONFIGS` ordering; documented in `summary.md` and README. |
| 4.3 | Reported comparisons isolate granularity, context, calibration, and full-vs-baseline | `[x]` | `COMPARISONS` (4 tuples with labels). |
| 4.4 | The design is described as **stepwise, not full-factorial** in the output | `[x]` | `_summary_lines()` protocol note; `summary.md` per model. |
| 4.5 | An unknown `--configs` name fails loudly | `[x]` | `run_experiment()` raises `SystemExit`; `TestRunExperimentOffline::test_unknown_config_raises_system_exit`. |
| 4.6 | A subset of configs can be run | `[x]` | `config_names` filter; CLI `--configs`. |

## 5. Split & round protocol (held-out, no leakage)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 5.1 | Split is **per-project (stratified)**, not global | `[x]` | `stratified_split()` iterates projects; `TestStratifiedSplit::test_counts_match_rule`. |
| 5.2 | `n_train = max(1, round(train_fraction × n_project))` | `[x]` | `stratified_split()`; same test (6/4 on two 5-story projects). |
| 5.3 | Capped so ≥1 test remains when a project has >1 story | `[x]` | `stratified_split()` cap; `TestStratifiedSplit::test_two_story_project_keeps_one_test`. |
| 5.4 | A 1-story project stays entirely in train (no empty test project) | `[x]` | `TestStratifiedSplit::test_single_story_project_all_train`. |
| 5.5 | Split is **deterministic** for a fixed seed | `[x]` | `TestStratifiedSplit::test_deterministic_with_same_seed`. |
| 5.6 | Committed 40-story sample → **24 train / 16 test** at seed 42, fraction 0.6 | `[~]` | `run_experiment` split summary; verified in the selftest run's `results.json`. |
| 5.7 | Calibration ratios are learned from the **train split only** | `[x]` | `compute_ratios(records["train"], …)` then applied to test; `TestComputeRatios`. |
| 5.8 | Nothing from the test split influences a prediction | `[x]` | Same; test split is never passed to `compute_ratios`. |
| 5.9 | `--rounds N` repeats each story N times and reports the **mean** over rounds | `[x]` | `_predict_story()` `statistics.fmean(estimates)`; `TestRunExperimentOffline::test_rounds_reported`. |
| 5.10 | The round nonce affects the **cache key only**, never the prompt text | `[x]` | `nonce = f"round-{r}"` enters `cache_key`, not `build_prompt`; `TestCacheKey`. |
| 5.11 | Stories with no ground-truth actual are dropped before splitting | `[x]` | `selected = [s for s in selected if s.id in actuals]`; `test_stories_without_actuals_are_dropped`. |

## 6. Multi-model comparison

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 6.1 | Default models are the three configured Groq models | `[x]` | `DEFAULT_MODELS = openai/gpt-oss-20b, openai/gpt-oss-120b, llama-3.3-70b-versatile`. |
| 6.2 | Models are configurable on the CLI and by parameter | `[x]` | `--models` (comma list); `run_experiment(models=…)`. |
| 6.3 | Each model is evaluated across **all** configs and compared independently | `[x]` | outer loop over `models`, inner over `selected_configs`; `results[model]`. |
| 6.4 | The per-model model identity is honoured by the live client | `[x]` | `GroqLlmClient(model=model)` override; `llm_client.py` `model` property. |
| 6.5 | `--models` comma-list is split and forwarded | `[x]` | `TestCliExperiment::test_splits_comma_lists_and_forwards_flags`. |

## 7. `experiment` command and outputs

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 7.1 | `python -m estimation_assistant experiment` runs the whole study | `[x]` | `__main__._cmd_experiment`; `TestCliExperiment`. |
| 7.2 | Flags: `--models --configs --projects --stories-per-project --rounds --seed --no-cache --selftest --output-dir` | `[x]` | `experiment` subparser in `__main__.py`. |
| 7.3 | Writes `results.json`, `results.csv`, `per_story.csv`, `summary.md`, `config_used.json`, `cache.json` | `[x]` | `write_outputs()` + `_save_cache()`; `TestRunExperimentOutputs::test_expected_files_written_no_stamp`. |
| 7.4 | `--no-cache` is forwarded and re-calls the model | `[x]` | `TestCliExperiment` forwards `--no-cache`; `TestCacheBehaviour::test_no_cache_always_calls`. |
| 7.5 | Second identical run is **all cache hits** (zero extra calls) | `[x]` | `TestCacheBehaviour::test_second_run_is_all_cache_hits`. |
| 7.6 | JSON output is standards-compliant (NaN/Inf serialised as `null`) | `[x]` | `_clean()` before dump. |
| 7.7 | A compact neutral console summary is printed after the run | `[x]` | `print_experiment_summary()`. |
| 7.8 | Optional figures are not required for a valid run (matplotlib optional) | `[!]` | No figure code is mandatory; the spec allows it to be absent. Metrics ship as tables. |

## 8. Dataset sampling

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 8.1 | The sampler is parameterised (`--n-projects`, `--stories-per-project`, `--seed`) | `[x]` | `scripts/generate_sample.py`; verified with `--help`. |
| 8.2 | Defaults reproduce the committed 40-story sample exactly (8 × 5, seed 42) | `[~]` | `DEFAULT_SEED/DEFAULT_N_PROJECTS/DEFAULT_PER_PROJECT`; committed sample is 8×5. |
| 8.3 | A no-argument run does not silently change the dataset | `[~]` | Defaults match the shipped sample; README documents this. |
| 8.4 | The experiment accepts the same subsetting (`--projects --stories-per-project --seed`) | `[x]` | `select_stories()`; `TestSelectAndGroup::{test_select_stories_caps_per_project, test_select_stories_project_filter, test_no_args_returns_all}`. |
| 8.5 | No-flag selection returns every story in stable order | `[x]` | `TestSelectAndGroup::test_no_args_returns_all`. |

## 9. Synthetic-path labelling (units / provenance)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 9.1 | The synthetic `demo` path (hours) is untouched by the experiment work | `[~]` | `demo`/`run-neodataset` unchanged; both suites still pass. |
| 9.2 | Experiment figures are labelled **story points**, matching NeoDataset ground truth | `[x]` | `_summary_lines()` "story points, not hours" note. |
| 9.3 | The four experiment prompts use `POINTS`/`ESTIMATE`, never `HOURS` | `[x]` | `prompts/experiment_*.txt`. |
| 9.4 | Baseline constants (16%/60%) are not altered or reused as results | `[~]` | `evaluation_agent.py` constants untouched; the experiment reports its own MAE/MAPE, not a paper number. |
| 9.5 | No claim of superiority is made before data exists | `[x]` | Neutral wording in `summary.md`, README, and `print_experiment_summary`; verdicts are CI-gated (§4). |

## 10. State hygiene & delivery

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 10.1 | The experiment never reads/writes `data/calibration_history.json` or `data/learning_state.json` | `[x]` | `experiment.py` imports only `utils`/`llm_client`/`metrics`/`models`; calibration is in-memory. |
| 10.2 | The experiment never imports or runs the Calibration/Learning agents | `[x]` | No such imports in `experiment.py`. |
| 10.3 | The experiment never writes `output/agent_messages.log` | `[x]` | It calls `llm.send` directly, not the orchestrator. |
| 10.4 | `reset-state` restores `calibration_history.json` from `.bak` and deletes `learning_state.json` | `[x]` | `__main__._cmd_reset_state`; `TestCliResetState::test_restores_and_deletes`. |
| 10.5 | `reset-state` never touches curated data (actuals, profiles, sample) | `[x]` | Same test (only the two state files are modified). |
| 10.6 | Selftest output is written to a separate directory (`output/experiment_selftest/`) | `[x]` | `run_experiment` `default_out`; selftest stamps every file. |
| 10.7 | Every selftest file is stamped `SELFTEST - NOT RESULTS` (JSON first key, CSV comment, MD first line) | `[x]` | `write_outputs`/`_save_cache`/`_write_json`/`_write_csv`; `TestRunExperimentOutputs::test_selftest_stamps_every_file`. |
| 10.8 | The deliverable ZIP excludes `.env` and refuses to ship a real key | `[~]` | `scripts/make_delivery_zip.py` hard gate; `.env.example` is the only env file included. |
| 10.9 | `.env` is never read, printed, or logged; no key is written to any file | `[x]` | No experiment test or module opens `.env`; the client reads the key via `utils.load_api_key()`. |
| 10.10 | A missing key produces a friendly message, not a stack trace, and no run is attempted | `[x]` | `_default_llm_factory()` raises `SystemExit` with the console.groq.com/keys guidance. |

## 11. Offline tests (FakeLlmClient only)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 11.1 | Tests never touch the network and never need an API key | `[x]` | `FakeLlmClient` throughout; the experiment takes an `llm_factory`. |
| 11.2 | Tests never write into the real `output/` | `[x]` | Injection of `output_dir=tmp_path`; `tests/conftest.py` isolates `utils.OUTPUT_DIR`. |
| 11.3 | `FakeLlmClient` can vary replies by prompt and records every call | `[x]` | `FakeLlmClient(reply_fn=…)` + `.calls`; `tests/test_llm_client.py`. |
| 11.4 | The selftest reply is deterministic and clearly labelled as not-a-result | `[x]` | `_selftest_reply`; `TestSelftestReply` (determinism, task/issue shapes). |
| 11.5 | End-to-end offline run produces known metrics | `[x]` | `TestRunExperimentOffline::test_known_metrics_and_calibration_effect` (MAE 5/2/0; calibrated MAE 0 with global ratio 2). |
| 11.6 | The full pipeline beats the baseline in the crafted fixture and reports `treatment_better` | `[x]` | `test_full_pipeline_beats_baseline_comparison`. |
| 11.7 | The whole suite passes with no skips | `[x]` | `145 passed` (`pytest -q`). |

## 12. Configuration & fixed settings

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 12.1 | Settings are fixed **before** any result is seen and live in `config.yaml` `experiment:` block | `[x]` | `_DEFAULT_SETTINGS`; `config.yaml`. |
| 12.2 | Split seed 42, train fraction 0.6 | `[x]` | `_DEFAULT_SETTINGS`; `TestSettings::test_defaults_when_config_missing`. |
| 12.3 | Bootstrap 1000 resamples with a fixed seed | `[x]` | `_DEFAULT_SETTINGS` `bootstrap_resamples/bootstrap_seed`. |
| 12.4 | `ratio_stat` default `median`; clamp `[0.1, 10.0]` | `[x]` | `_DEFAULT_SETTINGS`; `TestComputeRatios::{test_clamped_high, test_clamped_low}`. |
| 12.5 | `max_description_chars` = 4000, applied with a visible marker | `[x]` | `truncate_description()`; `TestTruncateDescription` (short unchanged, long marked, 0 disables). |
| 12.6 | Experiment block overrides top-level / defaults | `[x]` | `experiment_settings()`; `TestSettings::test_experiment_block_overrides`. |
| 12.7 | `--seed` / `--rounds` CLI overrides are honoured | `[x]` | `run_experiment()` seed/rounds params; `test_rounds_reported`. |
| 12.8 | Settings are not tuned after seeing results | `[x]` | Settings are read from config at run start; `config_used.json` records exactly what was used. |

## 13. Honesty, reproducibility & acceptance

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 13.1 | Every reported number is derived from a real reply (or a labelled selftest stub) | `[x]` | `_predict_story`/`config_metrics`; no constant is inserted as a metric. |
| 13.2 | Nothing is fabricated, smoothed, or hardcoded | `[x]` | No literal metric anywhere; all via `error_metrics` over actual replies. |
| 13.3 | A run is reproducible from committed inputs + `config_used.json` | `[x]` | Fixed seeds; `cache.json` fully replays a prior run. |
| 13.4 | Comparative verdicts are CI-gated (helps only when the 95% CI excludes 0) | `[x]` | `compare_configs()` verdict logic; `TestCompareConfigs`. |
| 13.5 | Lead time / cost per comparison is recorded for the run | `[x]` | `result["elapsed_seconds"]`. |
| 13.6 | The existing five commands, GUI, and Word report still work | `[x]` | Full suite green; no changes to GUI/report modules. |
| 13.7 | The deliverable remains self-contained and offline-gradable | `[~]` | Committed sample + actuals; `make_delivery_zip.py` builds the archive. |

---

### Deliberate non-applicable items

- **§7.8 optional figures** — the spec makes plots optional; the framework
  ships metrics as tables/CSV and needs no plotting dependency, so there is no
  mandatory figure to assert.
- **§9.1 baseline untouched** — the synthetic `demo` path is intentionally left
  byte-compatible; its behaviour is covered by the pre-existing
  `test_orchestrator.py` / `test_estimation_agent.py`, not re-asserted here.

### How to re-verify end to end

```bash
.venv/bin/python -m pytest -q                              # all offline tests
.venv/bin/python -m estimation_assistant experiment --selftest   # plumbing, stamped
# live (needs a real GROQ_API_KEY in .env):
.venv/bin/python -m estimation_assistant experiment
.venv/bin/python -m estimation_assistant reset-state       # restore pristine state
```

A live run is the only thing that produces real figures. The selftest run
proves the plumbing and is stamped `SELFTEST - NOT RESULTS` so it can never be
mistaken for a result.
