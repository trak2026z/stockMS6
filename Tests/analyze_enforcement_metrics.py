#!/usr/bin/env python3
"""Calculate closed-loop enforcement metrics for one experiment.

Required files in EXPERIMENT_DIR:
  ban_events.csv
  request_attempts.csv

The experiment start is approximated by the timestamp of the first recorded
request attempt. The experiment end is start + --simulation_duration seconds.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BOT_TOKEN = "SCRAPER_BOT"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate BBR, HBR, NEU, BRSR, HRR and NRS."
    )
    parser.add_argument(
        "experiment_dir",
        type=Path,
        help="Directory containing ban_event_log.csv and request_attempt_log.csv.",
    )
    parser.add_argument(
        "--simulation_duration",
        "--simulation-duration",
        dest="simulation_duration",
        type=float,
        required=True,
        help="Nominal experiment duration in seconds.",
    )
    parser.add_argument(
        "--num-bots",
        "--num_bots",
        dest="num_bots",
        type=int,
        required=True,
        help="Number of scraper-bot users.",
    )
    parser.add_argument(
        "--num_humans",
        "--num-humans",
        dest="num_humans",
        type=int,
        required=True,
        help="Combined number of simulated-human users.",
    )
    return parser.parse_args()


def require_columns(df: pd.DataFrame, required: set[str], file_name: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{file_name} is missing columns: {', '.join(missing)}")


def parse_boolean(series: pd.Series, column: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    parsed = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False, "t": True, "f": False})
    )
    if parsed.isna().any():
        raise ValueError(f"Invalid Boolean values in column {column}")
    return parsed.astype(bool)


def is_bot_persona(series: pd.Series) -> pd.Series:
    return series.astype(str).str.upper().str.contains(BOT_TOKEN, na=False)


def read_inputs(experiment_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bans_path = experiment_dir / "ban_event_log.csv"
    requests_path = experiment_dir / "request_attempt_log.csv"

    for path in (bans_path, requests_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input file not found: {path}")

    bans = pd.read_csv(bans_path)
    requests = pd.read_csv(requests_path)

    require_columns(
        bans,
        {"userId", "userPersona", "banStartedAt", "banExpiresAt"},
        bans_path.name,
    )
    require_columns(
        requests,
        {"timestamp", "userId", "userPersona", "isBlocked"},
        requests_path.name,
    )

    bans["banStartedAt"] = pd.to_datetime(bans["banStartedAt"], utc=True, errors="raise", format='ISO8601')
    bans["banExpiresAt"] = pd.to_datetime(bans["banExpiresAt"], utc=True, errors="raise", format='ISO8601')
    requests["timestamp"] = pd.to_datetime(requests["timestamp"], utc=True, errors="raise", format='ISO8601')
    requests["isBlocked"] = parse_boolean(requests["isBlocked"], "isBlocked")

    if requests.empty:
        raise ValueError("request_attempts.csv contains no request attempts")
    if (bans["banExpiresAt"] <= bans["banStartedAt"]).any():
        raise ValueError("Every banExpiresAt must be later than banStartedAt")

    return bans, requests


def merge_intervals(intervals: list[tuple[pd.Timestamp, pd.Timestamp]]) -> float:
    """Return the length of the interval union in minutes."""
    if not intervals:
        return 0.0

    intervals.sort(key=lambda item: item[0])
    current_start, current_end = intervals[0]
    total_seconds = 0.0

    for start, end in intervals[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total_seconds += (current_end - current_start).total_seconds()
            current_start, current_end = start, end

    total_seconds += (current_end - current_start).total_seconds()
    return total_seconds / 60.0


def blocked_minutes(
    bans: pd.DataFrame,
    is_bot: bool,
    experiment_start: pd.Timestamp,
    experiment_end: pd.Timestamp,
) -> float:
    selected = bans[is_bot_persona(bans["userPersona"]) == is_bot]
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    # Merge intervals per user first. Bans belonging to different users must
    # contribute independently to the user-minute numerator.
    for _, user_bans in selected.groupby("userId", sort=False):
        user_intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        for ban in user_bans.itertuples(index=False):
            start = max(experiment_start, ban.banStartedAt)
            end = min(experiment_end, ban.banExpiresAt)
            if start < end:
                user_intervals.append((start, end))
        if user_intervals:
            # Store the already merged duration as a synthetic interval from zero.
            minutes = merge_intervals(user_intervals)
            intervals.append((experiment_start, experiment_start + pd.Timedelta(minutes=minutes)))

    return sum((end - start).total_seconds() / 60.0 for start, end in intervals)


def safe_ratio(numerator: float, denominator: float, name: str) -> float:
    if denominator <= 0:
        raise ValueError(f"Cannot calculate {name}: denominator is zero")
    return numerator / denominator


def calculate_metrics(
    bans: pd.DataFrame,
    requests: pd.DataFrame,
    simulation_duration: float,
    num_bots: int,
    num_humans: int,
) -> pd.DataFrame:
    if simulation_duration <= 0:
        raise ValueError("--simulation_duration must be positive")
    if num_bots <= 0 or num_humans <= 0:
        raise ValueError("--num-bots and --num_humans must be positive")

    experiment_start = requests["timestamp"].min()
    experiment_end = experiment_start + pd.Timedelta(seconds=simulation_duration)
    duration_minutes = simulation_duration / 60.0

    bot_blocked_minutes = blocked_minutes(bans, True, experiment_start, experiment_end)
    human_blocked_minutes = blocked_minutes(bans, False, experiment_start, experiment_end)
    bot_available_minutes = num_bots * duration_minutes
    human_available_minutes = num_humans * duration_minutes

    request_is_bot = is_bot_persona(requests["userPersona"])
    bot_requests = requests[request_is_bot]
    human_requests = requests[~request_is_bot]

    bbr = safe_ratio(bot_blocked_minutes, bot_available_minutes, "BBR")
    hbr = safe_ratio(human_blocked_minutes, human_available_minutes, "HBR")
    brsr = safe_ratio(float(bot_requests["isBlocked"].sum()), len(bot_requests), "BRSR")
    hrr = safe_ratio(float(human_requests["isBlocked"].sum()), len(human_requests), "HRR")

    return pd.DataFrame(
        [{
            "experimentStart": experiment_start.isoformat(),
            "experimentEnd": experiment_end.isoformat(),
            "simulationDurationSeconds": simulation_duration,
            "numBots": num_bots,
            "numHumans": num_humans,
            "BBR": bbr,
            "HBR": hbr,
            "NEU": bbr - hbr,
            "BRSR": brsr,
            "HRR": hrr,
            "NRS": brsr - hrr,
            "botAvailableMinutes": bot_available_minutes,
            "botBlockedMinutes": bot_blocked_minutes,
            "humanAvailableMinutes": human_available_minutes,
            "humanBlockedMinutes": human_blocked_minutes,
            "botRequestAttempts": len(bot_requests),
            "blockedBotRequests": int(bot_requests["isBlocked"].sum()),
            "humanRequestAttempts": len(human_requests),
            "blockedHumanRequests": int(human_requests["isBlocked"].sum()),
        }]
    )


def save_plots(metrics: pd.DataFrame, output_dir: Path) -> None:
    row = metrics.iloc[0]

    fig, ax = plt.subplots(figsize=(8, 5))
    names = ["BBR", "HBR", "BRSR", "HRR"]
    ax.bar(names, [row[name] for name in names])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Rate")
    ax.set_title("Enforcement rates")
    fig.tight_layout()
    fig.savefig(output_dir / "enforcement_rates.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    names = ["NEU", "NRS"]
    ax.bar(names, [row[name] for name in names])
    ax.axhline(0, linewidth=1)
    ax.set_ylim(-1, 1)
    ax.set_ylabel("Score")
    ax.set_title("Net enforcement scores")
    fig.tight_layout()
    fig.savefig(output_dir / "net_enforcement_scores.png", dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    experiment_dir = args.experiment_dir.resolve()
    output_dir = experiment_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    bans, requests = read_inputs(experiment_dir)
    metrics = calculate_metrics(
        bans,
        requests,
        args.simulation_duration,
        args.num_bots,
        args.num_humans,
    )
    metrics.to_csv(output_dir / "metrics.csv", index=False, float_format="%.8f")
    save_plots(metrics, output_dir)

    print(metrics[["BBR", "HBR", "NEU", "BRSR", "HRR", "NRS"]].to_string(index=False))
    print(f"Saved results to: {output_dir}")


if __name__ == "__main__":
    main()
