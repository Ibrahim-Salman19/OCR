import os
import ctypes.util
import sys


def check_dll(name):
    path = ctypes.util.find_library(name)
    if path:
        print(f"[OK] {name} found at: {path}")
        return True

    # Manually check common paths
    system32 = os.path.join(os.environ["SystemRoot"], "System32")
    potential_path = os.path.join(system32, name)
    if os.path.exists(potential_path):
        print(f"[OK] {name} found at: {potential_path}")
        return True

    print(f"[MISSING] {name} NOT found.")
    return False


print("--- DLL Check ---")
check_dll("vcruntime140.dll")
check_dll("msvcp140.dll")
check_dll("concrt140.dll")  # Often missing for Torch
check_dll("vcomp140.dll")  # OpenMP (Torch)

print("\n--- Python Environment ---")
print(f"Python: {sys.version}")
print(f"Prefix: {sys.prefix}")
