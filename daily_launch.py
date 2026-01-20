import subprocess
import sys
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def run(cmd):
    subprocess.run(cmd, cwd=PROJECT_DIR, shell=False)

def main():
    # 1. Refresh data
    run([PYTHON, "ingest.py"])

    # 2. Build HTML (serve.py will also try to serve; we just want index.html)
    run([PYTHON, "serve.py"])

    # 3. Open in Edge (InPrivate)
    index_file = PROJECT_DIR / "index.html"
    if index_file.exists():
        subprocess.Popen([
            EDGE_PATH,
            "--inprivate",
            index_file.as_uri()
        ])

if __name__ == "__main__":
    main()

