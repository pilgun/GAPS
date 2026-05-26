#!/bin/bash

# Check existence of exactly 2 command-line arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <output_logs_dir> <apps_path>"
    exit 1
fi

output_logs_dir="$1"
apps_path="$2"

apps=$(ls "$apps_path" | grep ".apk")

if [ ! -d "$output_logs_dir" ]; then
    mkdir -p "$output_logs_dir"
fi

for app in $apps; do
    echo $app 
    adb install -g "$apps_path/$app"

    package_name=$(aapt dump badging "$apps_path/$app" | grep "package: name=" | awk -F"'" '{print $2}')
    
    # timeout --kill-after=5m 5m python ./Guardian/run.py -a "$apps_path/$app" -t "interact with the application to maximize exploration"
    python ape.py -p $package_name --running-minutes 300 --ape sata

    echo "Command done"
    
    adb logcat -d -s GAPS > "$output_logs_dir/$app.log"
    adb logcat -c
    
    if [ -n "$package_name" ]; then
        adb uninstall "$package_name"
    else
        echo "Failed to extract package name for $app"
    fi
done
