#!/bin/bash

# Check existence of exactly 2 command-line arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <output_logs_dir> <apps_path> <device>"
    exit 1
fi

output_logs_dir="$1"
apps_path="$2"
device="$3"

apps=$(ls "$apps_path" | grep ".apk")

if [ ! -d "$output_logs_dir" ]; then
    mkdir -p "$output_logs_dir"
fi

for app in $apps; do
    echo "====================================="
    echo "[*] START APP: $app"
    echo "====================================="
 
    adb -s "$device" install -g "$apps_path/$app" 
	
    package_name=$(aapt dump badging "$apps_path/$app" | grep "package: name=" | awk -F"'" '{print $2}')
    
    if [ -z "$package_name" ]; then
	echo "Failed to extract package name for $app"
	continue
    fi

    adb -s "$device" logcat -c
    adb -s "$device"  logcat -s GAPS >> "$output_logs_dir/$app.log" &
    logcat_pid=$!

    start_time=$(date +%s)
    end_time=$((start_time + 30*60))

    run_count=0


    while [ "$(date +%s)" -lt "$end_time" ]; do
        now=$(date +%s)
        remaining=$((end_time - now))
        run_count=$((run_count + 1))

        echo "[*] Restart #$run_count for $app"
        echo "[*] Remaining seconds: $remaining"
	echo "====== RESTART #$run_count $(date '+%F %T') ======" >> "$output_logs_dir/$app.log"
        # lancia app
	adb -s "$device"  shell am force-stop "$package_name" >/dev/null 2>&1
        adb -s "$device"  shell monkey -p "$package_name" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
        sleep 2

        # lancia APE e lascialo girare al massimo per il tempo rimanente
        python ape-bin/ape.py -P "$package_name" --running-minutes 30 --ape sata &
        ape_pid=$!

        echo "[*] APE PID: $ape_pid"

        while kill -0 "$ape_pid" 2>/dev/null; do
            now=$(date +%s)

            if [ "$now" -ge "$end_time" ]; then
                echo "[*] 30 minutes reached, stopping APE"
                kill -9 "$ape_pid" 2>/dev/null
                wait "$ape_pid" 2>/dev/null
                break 2
            fi

            # controlla se app è viva
            pid=$(adb -s "$device" shell pidof "$package_name" 2>/dev/null | tr -d '\r')

            if [ -z "$pid" ]; then
                echo "[!] App crashed/stopped: $package_name"
                adb -s "$device"  logcat -d | grep -i "FATAL EXCEPTION\|AndroidRuntime\|Exception\|CRASH" >> "$output_logs_dir/$app.crash.txt"

                echo "[*] Killing APE because app is dead"
                kill -9 "$ape_pid" 2>/dev/null
                wait "$ape_pid" 2>/dev/null
                break
            fi

            sleep 2
        done

        echo "[*] APE terminated, relaunching if time remains..."
	sleep 2
    done

    echo "[*] Command done for $app"


    kill "$logcat_pid" 2>/dev/null
    wait "$logcat_pid" 2>/dev/null

    if [ -n "$package_name" ]; then
        adb -s "$device" uninstall "$package_name"
    else
        echo "Failed to extract package name for $app"
    fi
done
