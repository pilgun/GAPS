import re
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


TS_PATTERN = re.compile(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
EVENT_PATTERN = re.compile(r"METHOD=(.+)")  # method-level proxy coverage


def parse_time(ts: str) -> float:
    # Example: "03-13 20:22:37.523"
    _, time_part = ts.split()
    h, m, s = time_part.split(":")
    s, ms = s.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def extract_events(log_path: Path):
    events = []
    start_time = None

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            ts_match = TS_PATTERN.search(line)
            ev_match = EVENT_PATTERN.search(line)

            if not ts_match or not ev_match:
                continue

            t_abs = parse_time(ts_match.group(1))
            if start_time is None:
                start_time = t_abs

            t_rel = t_abs - start_time
            if t_rel < 0:
                # Defensive guard in case of malformed ordering
                continue

            event_id = ev_match.group(1).strip()
            events.append((t_rel, event_id))

    return events


def build_curve(events, universe, times):
    events = sorted(events, key=lambda x: x[0])
    seen = set()
    curve = []
    idx = 0
    denom = len(universe)

    for t in times:
        while idx < len(events) and events[idx][0] <= t:
            seen.add(events[idx][1])
            idx += 1
        curve.append(100.0 * len(seen) / denom if denom else 0.0)

    return np.array(curve, dtype=float)


def main():
    parser = argparse.ArgumentParser(
        description="Compute final average coverage across apps and runs."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root folder containing output_run1, output_run2, output_run3",
    )
    parser.add_argument(
        "--run-folders",
        nargs="+",
        default=["output_run1", "output_run2", "output_run3"],
        help="Run folders to process",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=1800,
        help="Maximum time horizon in seconds (default: 1800 = 30 min)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Sampling step in seconds",
    )
    args = parser.parse_args()

    root = Path(args.root)
    run_folders = args.run_folders
    times = np.arange(0, args.max_time + 1, args.step)

    # 1) Build per-app event sets across ALL runs.
    #    This is the key fix: denominator for an app is the union of the
    #    method events observed for that same app across the 3 runs.
    app_universes = {}   # app_name -> set(methods)
    run_events = {}      # run_folder -> {app_name: [(t, event), ...]}

    for run_folder in run_folders:
        folder = root / run_folder
        logs = sorted(folder.glob("*.apk.log"))
        print(f"Scanning {run_folder} ({len(logs)} apps)...")
        run_events[run_folder] = {}

        for log in logs:
            app_name = log.name
            events = extract_events(log)
            run_events[run_folder][app_name] = events

            if app_name not in app_universes:
                app_universes[app_name] = set()

            for _, ev in events:
                app_universes[app_name].add(ev)

    # 2) For each run, build one average curve across all apps in that run,
    #    using the cross-run universe for each app.
    run_avg_curves = []

    for run_folder in run_folders:
        app_curves = []
        apps_in_run = run_events.get(run_folder, {})
        print(f"Processing {run_folder} ({len(apps_in_run)} apps)...")

        for app_name, events in apps_in_run.items():
            universe = app_universes.get(app_name, set())
            if not universe:
                continue

            curve = build_curve(events, universe, times)
            app_curves.append(curve)

        if app_curves:
            run_avg = np.mean(app_curves, axis=0)
            run_avg_curves.append(run_avg)

    if not run_avg_curves:
        raise RuntimeError("No valid data found in the provided run folders.")

    # 3) Final average across the run-level average curves.
    final_avg = np.mean(run_avg_curves, axis=0)

    # 4) Save CSV
    csv_path = root / "final_coverage_fixed.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        f.write("time_seconds,time_minutes,final_average_coverage\n")
        for t, y in zip(times, final_avg):
            f.write(f"{int(t)},{t/60.0:.6f},{y:.6f}\n")

    # 5) Plot
    png_path = root / "final_coverage_fixed.png"
    plt.figure(figsize=(10, 6))
    plt.plot(times / 60.0, final_avg, linewidth=3, label="Final Average")
    plt.axvline(x=5, linestyle="--", label="5 min")

    plt.xlabel("Time (minutes)")
    plt.ylabel("Coverage (%)")
    plt.title("Average Coverage (Apps + Runs)")
    plt.xlim(0, args.max_time / 60.0)
    plt.ylim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=200)
    plt.show()

    print(f"Saved plot to: {png_path}")
    print(f"Saved CSV to:  {csv_path}")


if __name__ == "__main__":
    main()
