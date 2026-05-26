import sys

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


def to_java_signature(smali_sig):
    try:
        class_and_method, params_and_return = smali_sig.split(";->")
        class_name = class_and_method[1:].replace("/", ".")
        method_name, params_and_return = params_and_return.split("(")
        params, return_type = params_and_return.split(")")

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

        java_return_type = java_to_dalvik_type_reverse(return_type)

        return f"<{class_name}: {java_return_type} {method_name}({','.join(java_params)})>"

    except Exception:
        return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python convert_seed.py file.seed")
        sys.exit(1)

    seed_file = sys.argv[1]

    with open(seed_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            java_sig = to_java_signature(line)
            if java_sig:
                print(java_sig)


if __name__ == "__main__":
    main()
