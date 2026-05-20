import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# CONFIG
ROOT = "."
RUN_FOLDERS = ["output_run1", "output_run2", "output_run3"]
MAX_TIME = 1800  # 30 minutes
STEP = 1

TS_PATTERN = re.compile(r"(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)")
EVENT_PATTERN = re.compile(r"METHOD=(.+)")  # use METHOD as coverage unit

def parse_time(ts):
    _, time = ts.split()
    h, m, s = time.split(":")
    s, ms = s.split(".")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000

def extract_events(log_path):
    events = []
    start_time = None

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            ts_match = TS_PATTERN.search(line)
            ev_match = EVENT_PATTERN.search(line)

            if not ts_match or not ev_match:
                continue

            t_abs = parse_time(ts_match.group(1))

            if start_time is None:
                start_time = t_abs

            t_rel = t_abs - start_time

            event_id = ev_match.group(1).strip()
            events.append((t_rel, event_id))

    return events

def build_curve(events, universe, times):
    events = sorted(events, key=lambda x: x[0])
    seen = set()
    curve = []
    idx = 0

    for t in times:
        while idx < len(events) and events[idx][0] <= t:
            seen.add(events[idx][1])
            idx += 1
        curve.append(100 * len(seen) / len(universe) if universe else 0)

    return np.array(curve)

def main():
    root = Path(ROOT)
    times = np.arange(0, MAX_TIME + 1, STEP)

    run_avg_curves = []

    for run_folder in RUN_FOLDERS:
        folder = root / run_folder
        logs = list(folder.glob("*.apk.log"))

        print(f"Processing {run_folder} ({len(logs)} apps)...")

        app_curves = []

        for log in logs:
            events = extract_events(log)
            universe = set(e for _, e in events)
            curve = build_curve(events, universe, times)
            app_curves.append(curve)

        if not app_curves:
            continue

        run_avg = np.mean(app_curves, axis=0)
        run_avg_curves.append(run_avg)

    if not run_avg_curves:
        print("No data found.")
        return

    final_avg = np.mean(run_avg_curves, axis=0)

    # Plot ONLY final average
    plt.figure(figsize=(10,6))
    plt.plot(times/60, final_avg, linewidth=3, label="Final Average")
    plt.axvline(x=5, linestyle='--')

    plt.xlabel("Time (minutes)")
    plt.ylabel("Coverage (%)")
    plt.title("Average Coverage (Apps + Runs)")
    plt.xlim(0, 30)
    plt.ylim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.tight_layout()
    plt.savefig("final_coverage.png", dpi=200)
    plt.show()

if __name__ == "__main__":
    main()
