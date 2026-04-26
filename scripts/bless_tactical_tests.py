#!/usr/bin/env python3
import os
import shutil
import sys

def bless(case_name=None):
    results_dir = "tests/tactical_cases/results"
    golden_dir = "tests/tactical_cases/golden"
    
    if not os.path.exists(results_dir):
        print(f"Results directory {results_dir} not found.")
        return

    if not os.path.exists(golden_dir):
        os.makedirs(golden_dir)

    files_to_bless = []
    if case_name:
        json_file = f"{case_name}.json"
        if os.path.exists(os.path.join(results_dir, json_file)):
            files_to_bless.append(json_file)
        else:
            print(f"Result for {case_name} not found.")
            return
    else:
        # Bless all JSON files in results
        for f in os.listdir(results_dir):
            if f.endswith(".json"):
                files_to_bless.append(f)

    for f in files_to_bless:
        src = os.path.join(results_dir, f)
        dst = os.path.join(golden_dir, f)
        shutil.copy2(src, dst)
        print(f"Blessed: {f}")

if __name__ == "__main__":
    case = sys.argv[1] if len(sys.argv) > 1 else None
    bless(case)
