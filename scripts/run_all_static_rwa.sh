#!/usr/bin/env bash

OIFS="$IFS"
IFS=$'\n'

# Command-line arguments
if [[ $# -lt 3 ]]; then
	echo "Usage: $0 <app_path> <testing_seed_path> <output_data_dir> [files] [resume_from]"
	exit 1
fi

app_path=$1
testing_seed_path=$2
output_data_dir=$3
files=${4:-$(ls $app_path)}
resume_from=${5:-""}

resume=0
if [[ "$resume_from" == "" ]]; then
	resume=1
fi

for file in $files; do
	echo $file
	if [[ "$file" == "$resume_from" ]]; then
		resume=1
	fi
	if [ $resume -eq 1 ]; then
		app_name=$file
		uv run gaps static -i $app_path/$app_name/$app_name.apk -custom_seed $testing_seed_path/"$app_name"_instructions.txt -o $output_data_dir -l 100 -d &
		pid=$!
		start_time=$(date +%s.%N)
		max_ram_kb=0
		# Monitor RAM usage while the process is running
		while kill -0 "$pid" 2>/dev/null; do
			current_ram_kb=$(ps -o rss= -p "$pid" 2>/dev/null | awk '{print $1}')
			if [[ $current_ram_kb -gt $max_ram_kb ]]; then
				max_ram_kb=$current_ram_kb
			fi
			sleep 1
		done

		wait "$pid"
		return_code=$? # Capture the return code of the command
		end_time=$(date +%s.%N)

		execution_time=$( echo "$end_time - $start_time" | bc -l )
		max_ram_mb=$((max_ram_kb / 1024)) # Convert to MB

		# Save app name, execution time, RAM usage, and return code to stats.csv
		stats_file="$output_data_dir/stats_static.csv"
		if [ ! -f "$stats_file" ]; then
			echo "App Name,Analysis Time (s),Max RAM Usage (MB),Return Code" > "$stats_file"
		fi
		echo "$app_name,$execution_time,$max_ram_mb,$return_code" >> "$stats_file"
		echo "done"
		rm -rf /tmp/*.cache
	fi
done
