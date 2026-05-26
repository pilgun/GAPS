import os
import csv
import sys

testing_seeds_dir = "/home/same/code/gaps/datasets/androtest_seeds"


def to_java_signature(smali_sig):
    # Split the smali signature into class, method, and parameters
    class_and_method, params_and_return = smali_sig.split(";->")
    class_name = class_and_method[1:].replace(
        "/", "."
    )  # Remove 'L' and replace '/' with '.'
    method_name, params_and_return = params_and_return.split("(")
    params, return_type = params_and_return.split(")")

    # Convert parameters from smali to Java format
    java_params = []
    i = 0
    while i < len(params):
        if params[i] == "[":
            array_type = ""
            while params[i] == "[":
                array_type += "[]"
                i += 1
            if params[i] == "L":
                end = params.index(";", i)
                java_params.append(
                    params[i + 1 : end].replace("/", ".") + array_type
                )
                i = end + 1
            else:
                java_params.append(
                    java_to_dalvik_type_reverse(params[i]) + array_type
                )
                i += 1
        elif params[i] == "L":
            end = params.index(";", i)
            java_params.append(params[i + 1 : end].replace("/", "."))
            i = end + 1
        else:
            java_params.append(java_to_dalvik_type_reverse(params[i]))
            i += 1

    # Convert return type from smali to Java format
    java_return_type = java_to_dalvik_type_reverse(return_type)

    # Format the final Java signature
    return f"<{class_name}: {java_return_type} {method_name}({','.join(java_params)})>"


def java_to_dalvik_type_reverse(dtype):
    reverse_mapping = {
        "I": "int",
        "V": "void",
        "Z": "boolean",
        "C": "char",
        "B": "byte",
        "S": "short",
        "J": "long",
        "F": "float",
        "D": "double",
    }
    return reverse_mapping.get(dtype, dtype)


def extract_methods_from_seed(seed_file):
    with open(seed_file, "r") as f:
        return [line.strip() for line in f.readlines()]


def check_reachability(log_file, methods):
    with open(log_file, "r") as f:
        log_content = f.read()
    if log_content == "":
        print(f"Log file {log_file} is empty.")
        with open("missing.txt", "a") as missing_file:
            missing_file.write(
                f"{log_file.split("/")[-1].replace('.log', '')}\n"
            )
        return []
    reached = [method for method in methods if method in log_content]
    return reached


def main(logs_dir, testing_seeds_dir, output_csv):
    results = []

    for log_file in os.listdir(logs_dir):
        if not log_file.endswith(".apk.log"):
            continue
        app_name = log_file.replace(".apk.log", "")
        androtest_path = os.path.join(
            "/home/same/code/gaps/AndroLog/androtest", f"{app_name}.apk"
        )
        if log_file.endswith(".apk.log") and os.path.exists(androtest_path):
            seed_file = os.path.join(testing_seeds_dir, f"{app_name}.seed")
            if os.path.exists(seed_file):
                methods = extract_methods_from_seed(seed_file)
                java_methods = [
                    to_java_signature(method) for method in methods
                ]
                log_path = os.path.join(logs_dir, log_file)
                reached_methods = check_reachability(log_path, java_methods)
                results.append(
                    {
                        "app_name": app_name,
                        "reached_methods": len(reached_methods),
                    }
                )
            else:
                print(f"Seed file {seed_file} does not exist.")

    # Add percentage of reached methods to each result
    for result in results:
        result["percentage_reached"] = (
            (result["reached_methods"] / len(methods)) * 100
            if len(methods) > 0
            else 0
        )

    average_percentage = sum(
        result["percentage_reached"] for result in results
    ) / len(results)
    results.append(
        {
            "app_name": "Average",
            "reached_methods": "",
            "percentage_reached": "{:.2f}".format(average_percentage),
        }
    )
    print(f"Average percentage of reached methods: {average_percentage:.2f}%")

    # Write updated results to CSV
    with open(output_csv, "w", newline="") as csvfile:
        fieldnames = ["app_name", "reached_methods", "percentage_reached"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


# Example usage
if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python check_reachability.py <results_directory>")
        sys.exit(1)

    results_directory = sys.argv[1]
    subdirectories = [
        "output_run1", "output_run2", "output_run3"
    ]


    for subdir in subdirectories:
        subdir_path = os.path.join(results_directory, subdir)
        output_csv = subdir + "_reachability_stats.csv"
        main(subdir_path, testing_seeds_dir, output_csv)

    # Combine all reachability stats into a final CSV
    final_csv = os.path.join(results_directory, "final_reachability_stats.csv")
    all_results = []
    app_averages = {}

    for subdir in subdirectories:
        csv_file = subdir + "_reachability_stats.csv"
        if os.path.exists(csv_file):
            with open(csv_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["app_name"] != "Average":
                        all_results.append(row)
                        app_name = row["app_name"]
                        if app_name not in app_averages:
                            app_averages[app_name] = {
                                "reached_methods": 0,
                                "percentage_reached": 0.0,
                                "count": 0,
                            }
                        app_averages[app_name]["reached_methods"] += int(
                            row["reached_methods"]
                        )
                        app_averages[app_name]["percentage_reached"] += float(
                            row["percentage_reached"]
                        )
                        app_averages[app_name]["count"] += 1

    # Calculate the average for each app
    averaged_results = []
    for app_name, stats in app_averages.items():
        averaged_results.append(
            {
                "app_name": app_name,
                "reached_methods": stats["reached_methods"] // stats["count"],
                "percentage_reached": "{:.2f}".format(
                    stats["percentage_reached"] / stats["count"]
                ),
            }
        )

    # Calculate the overall average percentage
    if all_results:
        overall_average = sum(
            float(row["percentage_reached"]) for row in all_results
        ) / len(all_results)
        averaged_results.append(
            {
                "app_name": "Overall Average",
                "reached_methods": "",
                "percentage_reached": "{:.2f}".format(overall_average),
            }
        )

    # Write the final CSV
    with open(final_csv, "w", newline="") as csvfile:
        fieldnames = ["app_name", "reached_methods", "percentage_reached"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(averaged_results)

    print(f"Final reachability stats written to {final_csv}")
