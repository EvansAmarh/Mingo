# Mingo Blox learner impact

An analytics-engineering project that asks: **which learners gain the most from Mingo Blox STEAM, robotics and AI programmes, and who is at risk of dropping out?**

> **All data in this repository is synthetic.** No real learner data is used, stored or requested. See [Data protection](#data-protection).

## Status

| Phase | What | State |
|---|---|---|
| 0 | Project scaffold (dbt + DuckDB) | Done |
| 1 | Synthetic data generator with known ground truth | Done |
| 2 | Staging models | In progress (`stg_learners` still to write) |
| 3 | Mart `fct_learner_outcomes` + data tests | Planned |
| 4 | Group analysis and regression, checked against ground truth | Planned |
| 5 | Streamlit dashboard | Planned |
| 6 | GitHub Actions CI | Planned |

## Pipeline

```
scripts/generate_synthetic_data.py
        |  writes
        v
seeds/raw_*.csv  +  data/ground_truth.json
        |  dbt seed
        v
models/staging/stg_*        clean: dedupe, normalise codes, flag bad dates and scores
        |  dbt run
        v
models/marts/fct_learner_outcomes     one row per learner
        |
        v
scripts/analyse.py  ->  reports/results.json, results.md
        |
        v
app/streamlit_app.py
```

## The synthetic data

`scripts/generate_synthetic_data.py` simulates 640 learners (random seed 2026) across:

- **3 programmes:** School Robotics (8 sessions, 8 weeks), AI Basics (6 sessions, 6 weeks), Holiday Camp (10 sessions, 2 weeks).
- **4 sites:** Accra Central, Tema, Madina, Kasoa.
- **Learner fields:** gender, age group, school type, prior experience, device at home.

Known effects on skill gain are built in and saved to `data/ground_truth.json`, so the analysis can later be checked against the truth:

| Effect | Value |
|---|---|
| Base gain (School Robotics / AI Basics / Holiday Camp), at 80% attendance | 14 / 11 / 8 |
| Device at home | +4 |
| Prior experience | -3 |
| Per 10 points of attendance | +1.2 |
| Girls in public schools (extra) | -2.5 |

Device access is more common in private schools, so it is a **confounder**. A dropout is a learner absent for the last 3 sessions, and has no post score.

Realistic errors are planted so the cleaning and tests have something to catch: mixed gender codes, duplicate enrolments, site names with trailing spaces, an impossible score of 105, and an attendance date before its programme starts.

## How to run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

.\.venv\Scripts\python scripts/generate_synthetic_data.py
.\.venv\Scripts\dbt seed --profiles-dir .
.\.venv\Scripts\dbt run --profiles-dir .
```

Later phases add `dbt test`, `python scripts/analyse.py` and `streamlit run app/streamlit_app.py`. The DuckDB warehouse is created at `data/warehouse.duckdb` and is not committed.

## Conventions

- SQL: lowercase keywords, CTEs over subqueries, every model uses `{{ ref() }}`.
- Every model has a description and tests in `schema.yml`.
- Python: functions with docstrings, fixed seed (2026), no notebooks in the pipeline.
- Every finding is reported with a 95% interval and its group size. Groups under 30 learners are never reported on their own.

## Limits

There is no comparison group, so this shows **who gains more, not what causes the gain**. Even with the synthetic truth known, real programme data would carry selection effects (who enrols, who stays) that this design cannot remove.

## Data protection

Learners at Mingo Blox are children. Real learner data would need management approval, parental consent and compliance with Ghana's Data Protection Act, 2012 (Act 843). This project therefore uses synthetic data only.

## Stack

Python 3.11+, pandas, numpy, statsmodels, dbt-core with dbt-duckdb, DuckDB, Streamlit.
