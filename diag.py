import sys
import os
print(f"CWD: {os.getcwd()}")
sys.path.append(os.getcwd())

try:
    print("Attempting to import src.main...")
    import src.main
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
