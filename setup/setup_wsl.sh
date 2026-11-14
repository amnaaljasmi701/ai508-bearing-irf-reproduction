#!/usr/bin/env bash
# One-time environment setup inside WSL2 Ubuntu 22.04.
# Run from the repository root:  bash setup/setup_wsl.sh
set -euo pipefail

echo "== system packages (Java 17, Python 3.11) =="
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk-headless software-properties-common curl unzip
if ! command -v python3.11 >/dev/null 2>&1; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

echo "== virtual environment =="
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
pip install -e .

JAVA_HOME_DIR=$(dirname "$(dirname "$(readlink -f "$(which java)")")")
if ! grep -q "JAVA_HOME" ~/.bashrc; then
  echo "export JAVA_HOME=${JAVA_HOME_DIR}" >> ~/.bashrc
fi
export JAVA_HOME=${JAVA_HOME_DIR}

echo "== check =="
python scripts/00_check_env.py
echo "Done. Next time run:  source .venv/bin/activate"
