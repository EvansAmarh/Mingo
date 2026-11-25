"""Generate SYNTHETIC Mingo Blox learner data with known, planted effects.

No real learner data is used anywhere. The true effects are written to
data/ground_truth.json so analyse.py can check whether it recovers them.
Run from the project root:  python scripts/generate_synthetic_data.py
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
N_LEARNERS = 640

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "seeds"
DATA = ROOT / "data"

# ---- The known truth (change these, rerun, and the estimates should move) ----
BASE_GAIN = {"School Robotics": 14.0, "AI Basics": 11.0, "Holiday Camp": 8.0}
DEVICE_EFFECT = 4.0
PRIOR_EXPERIENCE_EFFECT = -3.0
ATTENDANCE_PER_10_POINTS = 1.2
GIRL_PUBLIC_EFFECT = -2.5
ATTENDANCE_CENTRE = 80.0   # base gain is the gain at 80% attendance
NOISE_SD = 4.0

PROGRAMMES = {
    # name: (programme_id, sessions, weeks, start_date)
    "School Robotics": ("P1", 8, 8, date(2026, 1, 19)),
    "AI Basics": ("P2", 6, 6, date(2026, 2, 2)),
    "Holiday Camp": ("P3", 10, 2, date(2026, 4, 6)),
}
SITES = ["Accra Central", "Tema", "Madina", "Kasoa"]
P_DEVICE = {"private": 0.75, "public": 0.30}   # device is a confounder
P_PRIVATE = 0.40
P_MISSED_FIRST_TWO = 0.15
P_DROPOUT = {True: 0.45, False: 0.10}          # early-warning signal


def session_dates(start: date, sessions: int, weeks: int) -> list[date]:
    """Return one date per session: weekly, or 5 weekdays a week for the camp."""
    if sessions == weeks:
        return [start + timedelta(days=7 * i) for i in range(sessions)]
    per_week = sessions // weeks
    return [start + timedelta(days=7 * (i // per_week) + i % per_week) for i in range(sessions)]


def simulate_learners(rng: np.random.Generator) -> pd.DataFrame:
    """Draw learner attributes (clean, before errors are planted)."""
    names = list(PROGRAMMES)
    school = rng.choice(["private", "public"], N_LEARNERS, p=[P_PRIVATE, 1 - P_PRIVATE])
    device = np.array([rng.random() < P_DEVICE[s] for s in school])
    return pd.DataFrame({
        "learner_id": [f"L{i:04d}" for i in range(1, N_LEARNERS + 1)],
        "programme_name": rng.choice(names, N_LEARNERS, p=[0.45, 0.30, 0.25]),
        "site": rng.choice(SITES, N_LEARNERS),
        "gender": rng.choice(["F", "M"], N_LEARNERS),
        "age_group": rng.choice(["8-10", "11-13", "14-17"], N_LEARNERS, p=[0.30, 0.45, 0.25]),
        "school_type": school,
        "prior_experience": rng.random(N_LEARNERS) < 0.30,
        "device_at_home": device,
    })


def simulate_attendance(rng: np.random.Generator, learners: pd.DataFrame):
    """Build the attendance grid and flag dropouts (absent for the last 3 sessions)."""
    rows, att_pct, dropped = [], {}, {}
    for r in learners.itertuples():
        _, n, weeks, start = PROGRAMMES[r.programme_name]
        dates = session_dates(start, n, weeks)
        p_attend = rng.beta(8, 2)  # learner's usual attendance, mean ~0.8
        present = rng.random(n) < p_attend
        missed_first_two = rng.random() < P_MISSED_FIRST_TWO
        if missed_first_two:
            present[:2] = False
        drops = rng.random() < P_DROPOUT[missed_first_two]
        if drops:
            first_absent = rng.integers(0, n - 2)  # 0..n-3, so at least 3 absences in a row at the end
            present[first_absent:] = False
        elif not present[-3:].any():
            present[-1] = True  # non-dropouts show up at least once at the end
        dropped[r.learner_id] = not present[-3:].any()
        att_pct[r.learner_id] = 100 * present.mean()
        for i in range(n):
            rows.append((r.learner_id, i + 1, dates[i], "yes" if present[i] else "no"))
    attendance = pd.DataFrame(rows, columns=["learner_id", "session_number", "session_date", "attended"])
    return attendance, att_pct, dropped


def simulate_scores(rng: np.random.Generator, learners: pd.DataFrame, att_pct: dict, dropped: dict) -> pd.DataFrame:
    """Compute pre/post scores from the true effects. Dropouts get no post score."""
    rows = []
    for r in learners.itertuples():
        girl = r.gender == "F"
        public = r.school_type == "public"
        pre = np.clip(rng.normal(40 + 6 * r.prior_experience, 10), 5, 95)
        gain = (BASE_GAIN[r.programme_name]
                + DEVICE_EFFECT * r.device_at_home
                + PRIOR_EXPERIENCE_EFFECT * r.prior_experience
                + ATTENDANCE_PER_10_POINTS * (att_pct[r.learner_id] - ATTENDANCE_CENTRE) / 10
                + GIRL_PUBLIC_EFFECT * (girl and public)
                + rng.normal(0, NOISE_SD))
        if dropped[r.learner_id]:
            post, done = np.nan, "no"
        else:
            post = float(np.clip(round(pre + gain), 0, 100))
            done = "yes" if rng.random() < min(0.95, 0.3 + att_pct[r.learner_id] / 150) else "no"
        rows.append((r.learner_id, round(pre), post, done))
    return pd.DataFrame(rows, columns=["learner_id", "pre_score", "post_score", "project_completed"])


def plant_errors(rng, enrolments, attendance, assessments):
    """Corrupt the raw tables the way real registers get corrupted."""
    enrolments = enrolments.copy()
    idx = rng.choice(len(enrolments), 40, replace=False)
    enrolments.loc[idx, "gender"] = enrolments.loc[idx, "gender"].map({"F": "Female", "M": "Male"})
    idx = rng.choice(len(enrolments), 15, replace=False)
    enrolments.loc[idx, "site"] = enrolments.loc[idx, "site"] + " "
    dupes = enrolments.sample(12, random_state=SEED)
    enrolments = pd.concat([enrolments, dupes], ignore_index=True)

    assessments = assessments.copy()
    scored = assessments.index[assessments["post_score"].notna()]
    assessments.loc[rng.choice(scored), "post_score"] = 105

    attendance = attendance.copy()
    i = rng.integers(len(attendance))
    start = min(p[3] for p in PROGRAMMES.values())
    attendance.loc[i, "session_date"] = start - timedelta(days=30)

    # YOU WRITE: plant one more error of your own here (e.g. an impossible age group).
    return enrolments, attendance, assessments


def main() -> None:
    """Generate the four seed CSVs and ground_truth.json."""
    rng = np.random.default_rng(SEED)
    learners = simulate_learners(rng)
    attendance, att_pct, dropped = simulate_attendance(rng, learners)
    assessments = simulate_scores(rng, learners, att_pct, dropped)

    programmes = pd.DataFrame([
        (pid, name, n, w, start, start + timedelta(days=7 * w - 1))
        for name, (pid, n, w, start) in PROGRAMMES.items()
    ], columns=["programme_id", "programme_name", "n_sessions", "duration_weeks", "start_date", "end_date"])

    enrolments = learners.merge(programmes[["programme_id", "programme_name"]], on="programme_name")
    enrolments = enrolments.drop(columns="programme_name").sort_values("learner_id")
    enrolments["prior_experience"] = np.where(enrolments["prior_experience"], "yes", "no")
    enrolments["device_at_home"] = np.where(enrolments["device_at_home"], "yes", "no")
    enrolments = enrolments[["learner_id", "programme_id", "site", "gender", "age_group",
                             "school_type", "prior_experience", "device_at_home"]].reset_index(drop=True)

    enrolments, attendance, assessments = plant_errors(rng, enrolments, attendance, assessments)

    SEEDS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    enrolments.to_csv(SEEDS / "raw_enrolments.csv", index=False)
    programmes.to_csv(SEEDS / "raw_programmes.csv", index=False)
    attendance.to_csv(SEEDS / "raw_attendance.csv", index=False)
    assessments.to_csv(SEEDS / "raw_assessments.csv", index=False)

    truth = {
        "note": "SYNTHETIC data. True effects on skill gain (points).",
        "seed": SEED,
        "n_learners": N_LEARNERS,
        "base_gain_at_80pct_attendance": BASE_GAIN,
        "device": DEVICE_EFFECT,
        "prior_experience": PRIOR_EXPERIENCE_EFFECT,
        "attendance_per_10_points": ATTENDANCE_PER_10_POINTS,
        "girl": 0.0,
        "public_school": 0.0,
        "girl_x_public": GIRL_PUBLIC_EFFECT,
        "noise_sd": NOISE_SD,
        "planted_errors": {"mixed_gender_codes": 40, "duplicate_enrolments": 12,
                           "site_trailing_spaces": 15, "score_over_100": 1,
                           "attendance_before_start": 1},
    }
    (DATA / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print(f"enrolments={len(enrolments)} attendance={len(attendance)} "
          f"assessments={len(assessments)} dropouts={sum(dropped.values())}")


if __name__ == "__main__":
    main()
