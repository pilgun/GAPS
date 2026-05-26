#!/bin/bash

# Check existence of exactly 2 command-line arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <output_logs_dir> <apps_path> <device>"
    exit 1
fi

output_logs_dir="$1"
apps_path="$2"
device="$3"

SEEDS_DIR="/home/stefano/Desktop/seeds"

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

	txt_file="$SEEDS_DIR/${app%.apk}.txt"

	if [ -f "$txt_file" ]; then
    		methods=$(shuf "$txt_file" | head -n 10 | sed 's/^/- /')
	else
    		methods="- no targets available"
	fi

        PROMPT="You are an automated Android UI testing agent. Your objective is to explore the application and try to reach the following target methods: $methods . Focus on meaningful UI interactions, navigation flows and triggering app logic. Reach target methods efficiently."


	# lancia APE e lascialo girare al massimo per il tempo rimanente
        timeout "$remaining" python run.py -a "$apps_path/$app" -t "$PROMPT"  -m 200 >> "$output_logs_dir/$app.log" 2>&1 &
        gu_pid=$!

        echo "[*] GUARDIAN PID: $gu_pid"

        while kill -0 "$gu_pid" 2>/dev/null; do
            now=$(date +%s)

            if [ "$now" -ge "$end_time" ]; then
                echo "[*] 30 minutes reached, stopping GUARDIAN"
                kill -9 "$gu_pid" 2>/dev/null	
                wait "$gu_pid" 2>/dev/null
                break 2
            fi

            # controlla se app è viva
            pid=$(adb -s "$device" shell pidof "$package_name" 2>/dev/null | tr -d '\r')

            if [ -z "$pid" ]; then
                echo "[!] App crashed/stopped: $package_name"
                adb -s "$device"  logcat -d | grep -i "FATAL EXCEPTION\|AndroidRuntime\|Exception\|CRASH" >> "$output_logs_dir/$app.crash.txt"

                echo "[*] Killing GUARDIAN because app is dead"
                kill -9 "$gu_pid" 2>/dev/null
                wait "$gu_pid" 2>/dev/null
                break
            fi

            sleep 2
        done

        echo "[*] GUARDIAN terminated, relaunching if time remains..."
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
