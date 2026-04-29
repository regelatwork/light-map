import os
import subprocess
import sys


def test_tactical_golden_cases():
    """
    Wrapper for running tactical golden-master tests.
    Discovers all .yaml cases in tests/tactical_cases and executes the runner.
    """
    runner_path = os.path.join("scripts", "run_tactical_tests.py")

    # Run the script as a subprocess to keep the test environment clean
    result = subprocess.run(
        [sys.executable, runner_path],
        capture_output=True,
        text=True
    )

    # If the script failed, print its output and fail the test
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise AssertionError("Tactical golden tests failed. See output above for mismatch details and blessing instructions.")
    else:
        # Script passed
        print(result.stdout)
        assert True
