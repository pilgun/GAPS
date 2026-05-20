#!/usr/bin/env bash

OIFS="$IFS"
IFS=$'\n'

# Command-line arguments
if [[ $# -lt 2 ]]; then
	echo "Usage: $0 <app_path> <output_dir> [files] [resume_from]"
	exit 1
fi

app_path=$1
output_dir=$2
files=${3:-$(ls $app_path)}
resume_from=${4:-""}

resume=0
if [[ "$resume_from" == "" ]]; then
	resume=1
fi
# Initialize the CSV file if it doesn't exist
stats_file="$output_dir/stats_run.csv"
if [[ ! -f "$stats_file" ]]; then
	echo "App Name,Execution Time (s)" > "$stats_file"
fi

for file in $files; do
	echo $file
	app_name=$file
	if [[ "$file" == "$resume_from" ]]; then
		resume=1
	fi
	if [ $resume -eq 1 ]; then
		start_time=$(date +%s.%N)
		uv run gaps run -i $app_path/$app_name/$app_name.apk -instr $output_dir/$app_name/$app_name-instr.json -o $output_dir -frida
		end_time=$(date +%s.%N)
		execution_time=$(echo "$end_time - $start_time" | bc)
		echo "$app_name,$execution_time" >> "$stats_file"
	fi
	echo "done"
done

