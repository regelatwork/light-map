try:
    import numba
    print("Numba imported successfully. HAS_NUMBA = True")
except ImportError as e:
    print(f"Numba import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")

import sys


print(f"Current PYTHONPATH: {sys.path}")

try:
    import scripts
    print("Scripts module imported successfully")
except ImportError as e:
    print(f"Scripts import failed: {e}")
