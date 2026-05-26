#!/bin/bash

# Check existence of exactly 2 command-line arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <output_logs_dir> <apps_path> <device>"
    exit 1
fi

output_logs_dir="$1"
apps_path="$2"
device="$3"

reset_environment() {
	echo "[*] FULL RESET"
        
	#adb -s "$device" emu kill 2>/dev/null
	#sleep 5
	#emulator -avd android23 -wipe-data -no-snapshot-load &
	#sleep 20
	#adb wait-for-device

	#while [[  "$(adb shell getprop sys.boot_completed 2>/dev/null)" != "1"  ]]; do
	#    sleep 2
	#done

	#sleep 5
	pkill -f run_stoat_testing.rb 2>/dev/null
	pkill -f stoat 2>/dev/null

	rm -rf Stoat/tmp/*
	rm -rf Stoat/output/*
	rm -rf Stoat/logs/*
	rm -rf Stoat/workspace/*
	rm -rf ~/.stoat 2>/dev/null

	find . -name "*.stg" -delete 2>/dev/null
	find . -name "*.xml" -delete 2>/dev/null
	find . -name "*.json" -delete 2>/dev/null

	rm -rf /tmp/stoat* 2>/dev/null
        rm -rf /tmp/ge* 2>/dev/null

	adb -s "$device" shell rm  -fr /data/local/tmp/* 2>/dev/null
	adb -s "$device" shell rm  -fr /sdcard/* 2>/dev/null

	echo "[*] RESET DONE"
}

apps=$(ls "$apps_path" | grep ".apk")
#apps=$(cat missing.txt)

if [ ! -d "$output_logs_dir" ]; then
    mkdir -p "$output_logs_dir"
fi

#cleanup
fuser -k 2000/tcp 2>/dev/null
pkill -f SocketServer 2>/dev/null
#pkill -f rec.rb 2>/dev/null
#pkill -f analyzeAndroidApk.sh 2>/dev/null
sleep 2

for app in $apps; do
    echo "====================================="
    echo "[*] START APP: $app"
    echo "====================================="
    reset_environment
    adb -s "$device" uninstall "$package_name" 2>/dev/null 

    appname=$(echo "$app" | sed 's/\.apk$//')
    adb -s "$device" install -r -g "$apps_path/$app" 
    package_name=$(aapt dump badging "$apps_path/$app" | grep "package: name=" | awk -F"'" '{print $2}')
    echo "[*] Extracted package $package_name"

    if [ -z "$package_name" ]; then
        echo "Failed to extract package name for $app"
        continue
    fi

    start_time=$(date +%s)
    end_time=$((start_time + 30*60))
    run_count=0

    while [ "$(date +%s)" -lt "$end_time" ]; do
        now=$(date +%s)
        remaining=$((end_time - now))
        run_count=$((run_count + 1))

	adb -s "$device" logcat -c

        adb -s "$device" logcat -s GAPS >> "$output_logs_dir/$app.log" &
        logcat_pid=$!


        echo "[*] Restart #$run_count for $app"
        echo "[*] Remaining seconds: $remaining"
        echo "====== RESTART #$run_count $(date '+%F %T') ======" >> "$output_logs_dir/$app.log"

	touch "$output_logs_dir/other/${appname}_stg.xml"

	# lancia GE e lascialo girare al massimo per il tempo rimanente
        timeout "${remaining}s" ruby Stoat/bin/run_stoat_testing.rb --avd_name="$device" --apk_path="$apps_path/$app" --stg="$output_logs_dir/other/${appname}_stg.xml" >> "$output_logs_dir/other/$app.stoat.log" 2>&1 &
        ge_pid=$!


	while kill -0 "$ge_pid" 2>/dev/null; do
            now=$(date +%s)

            if ! kill -0 "$ge_pid" 2>/dev/null; then
                echo "[*] GE dead, restart loop..."
                break 
            fi

            if [ "$now" -ge "$end_time" ]; then
                echo "[*] 30 minutes reached, stopping GoalExplorer"
                kill -9 "$ge_pid" 2>/dev/null
                wait "$ge_pid" 2>/dev/null
                break 2
            fi

            # controlla se app è viva
            pid=$(adb -s "$device" shell pidof "$package_name" 2>/dev/null | tr -d '\r')

            if [ -z "$pid" ]; then
                echo "[!] App crashed/stopped: $package_name"
                adb -s "$device"  logcat -d AndroidRuntime:E *:S >> "$output_logs_dir/other/$app.crash.txt"

                echo "[*] Killing GoalExplorer because app is dead"
                kill -9 "$ge_pid" 2>/dev/null
                wait "$ge_pid" 2>/dev/null
                break
            fi

            sleep 2
        done

	kill "$logcat_pid" 2>/dev/null
        wait "$logcat_pid" 2>/dev/null

	echo "[*] Restarting because app crashed"
	sleep 2
    done

    echo "[*] Command done for $app"


    if [ -n "$package_name" ]; then
        echo "[*] Package name : $package_name"
	adb -s "$device" shell am force-stop "$package_name" || echo "force-stop failed"
    else
        echo "Failed to extract package name for $app"
    fi
done
