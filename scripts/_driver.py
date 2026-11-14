"""Helper: launch run_single.py in a subprocess so every setting gets a clean JVM."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def launch(**kw):
    cmd = [sys.executable, os.path.join(HERE, "run_single.py")]
    for k, v in kw.items():
        cmd += [f"--{k}", str(v)]
    print(">>", " ".join(cmd[1:]), flush=True)
    subprocess.run(cmd, check=True)
