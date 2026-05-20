from os import times
import re
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

# Parse lines like:
# 03-13 20:22:37.523  7424  7424 D GAPS    : METHOD=<a2dp.Vol.main: void onCreate(android.os.Bundle)>
TS_PATTERN = re.compile(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
METHOD_PATTERN = re.compile(r"METHOD=(.+)")


def parse_time(ts: str) -> float:
    # "03-13 20:22:37.523" -> seconds in day
    _, time_part = ts.split()
    h, m, s = time_part.split(":")
    s, ms = s.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def extract_methods(log_path: Path):
    """
    Extract cumulative method-hit events from one .apk.log file.
    Restart blocks remain part of the same run, exactly as in the user's setup.
    """
    events = []
    first_ts = None

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            ts_match = TS_PATTERN.search(line)
            meth_match = METHOD_PATTERN.search(line)
            if not ts_match or not meth_match:
                continue

            t_abs = parse_time(ts_match.group(1))
            if first_ts is None:
                first_ts = t_abs

            t_rel = t_abs - first_ts
            if t_rel < 0:
                # Defensive: skip weird wraparound / malformed ordering
                continue

            method_id = meth_match.group(1).strip()
            events.append((t_rel, method_id))

    return events


def build_curve(events, denominator_set, times):
    """
    Coverage(t) = unique methods seen up to t / denominator
    """
    events = sorted(events, key=lambda x: x[0])
    seen = set()
    curve = []
    idx = 0
    denom = len(denominator_set)

    for t in times:
        while idx < len(events) and events[idx][0] <= t:
            seen.add(events[idx][1])
            idx += 1

        curve.append(100.0 * len(seen) / denom if denom else 0.0)

    return np.array(curve, dtype=float)


def main():
    parser = argparse.ArgumentParser(
        description="Compute final average time-vs-coverage curve from your own run results."
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Folder containing output_run1, output_run2, output_run3",
    )
    parser.add_argument(
        "--runs",
        nargs="+",
        default=["output_run1", "output_run2", "output_run3"],
        help="Run folders",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=1800,
        help="Maximum analysis time in seconds (default 1800 = 30 min)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Sampling step in seconds",
    )
    parser.add_argument(
        "--save-run-curves",
        action="store_true",
        help="Also save the 3 average run curves in a secondary plot",
    )
    args = parser.parse_args()

    root = Path(args.root)
    run_folders = args.runs
    times = np.arange(0, args.max_time + 1, args.step)

    # 1) Read all logs, grouped by app and run
    # run_events[run_folder][app_name] = [(t, method), ...]
    run_events = {}
    # app_universe[app_name] = union of methods seen for that app across all runs
    app_universe = {}

    for run_folder in run_folders:
        folder = root / run_folder
        logs = sorted(folder.glob("*.apk.log"))
        print(f"Scanning {run_folder}: {len(logs)} apps")
        run_events[run_folder] = {}

        for log_path in logs:
            app_name = log_path.name
            events = extract_methods(log_path)
            run_events[run_folder][app_name] = events

            if app_name not in app_universe:
                app_universe[app_name] = set()
            for _, method_id in events:
                app_universe[app_name].add(method_id)

    # 2) Average over apps, separately for each run
    run_avg_curves = []
    run_avg_map = {}

    for run_folder in run_folders:
        app_curves = []
        for app_name, events in run_events[run_folder].items():
            denom_set = app_universe.get(app_name, set())
            curve = build_curve(events, denom_set, times)
            app_curves.append(curve)

        if app_curves:
            avg_curve = np.mean(app_curves, axis=0)
            run_avg_curves.append(avg_curve)
            run_avg_map[run_folder] = avg_curve
            print(f"Processed {run_folder}: averaged {len(app_curves)} app curves")
        else:
            print(f"Warning: no valid app curves in {run_folder}")

    if not run_avg_curves:
        raise RuntimeError("No valid data found.")

    # 3) Final average over runs
    final_avg = np.mean(run_avg_curves, axis=0)

    # 4) Save CSV
    csv_path = root / "final_average_from_my_runs.csv"
    with csv_path.open("w", encoding="utf-8") as f:
        header = ["time_seconds", "time_minutes"]
        for run_folder in run_folders:
            if run_folder in run_avg_map:
                header.append(f"{run_folder}_avg")
        header.append("final_avg")
        f.write(",".join(header) + "\n")

        for i, t in enumerate(times):
            row = [str(int(t)), f"{t/60.0:.6f}"]
            for run_folder in run_folders:
                if run_folder in run_avg_map:
                    row.append(f"{run_avg_map[run_folder][i]:.6f}")
            row.append(f"{final_avg[i]:.6f}")
            f.write(",".join(row) + "\n")

    # 5) Final plot: exactly one final curve, coherent with the user's interpretation
    final_pdf = root / "ape_runs.pdf"
    plt.figure(figsize=(10, 6))
    plt.plot(times / 60.0, final_avg, linewidth=3, label="Final average")
    plt.axvline(x=5, linestyle="--", label="5 min")
    # horizontal line at highest reached value and label on y-axis
    max_val = float(np.max(final_avg))
    plt.axhline(y=max_val, linestyle=":", color="gray",
                label=f"Max {max_val:.2f}%")
    plt.xlabel("Time (minutes)")
    plt.ylabel(f"Coverage (%) — max {max_val:.2f}%")
    plt.title("Average Coverage from APE (3 runs)")
    plt.xlim(0, args.max_time / 60.0)
    plt.ylim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(final_pdf, dpi=200)

    # 6) Optional debug plot with the 3 run-average curves
    if args.save_run_curves:
        debug_pdf = root / f"{args.root}_run_average_curves_from_my_runs.pdf"
        plt.figure(figsize=(10, 6))
        for run_folder, curve in run_avg_map.items():
            plt.plot(times / 60.0, curve, label=run_folder)
        plt.axvline(x=5, linestyle="--", label="5 min")
        # add horizontal line for highest reached among run averages
        max_debug = float(np.max(list(run_avg_map.values())))
        plt.axhline(y=max_debug, linestyle=":", color="gray",
                    label=f"Max {max_debug:.2f}%")
        plt.xlabel("Time (minutes)")
        plt.ylabel(f"Coverage (%) — max {max_debug:.2f}%")
        plt.title("Average Coverage per Run (debug)")
        plt.xlim(0, args.max_time / 60.0)
        plt.ylim(0, 100)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(debug_pdf, dpi=200)
        print(f"Saved debug run plot to: {debug_pdf}")

    print(f"Saved final plot to: {final_pdf}")
    print(f"Saved CSV to:       {csv_path}")
    plt.show()


if __name__ == "__main__":
    main()
