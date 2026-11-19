#!/usr/bin/env bash
# One-command bootstrap for the Resume AI development environment.
#
#   ./scripts/setup_env.sh
#
# Creates the conda env, installs the Python dependencies, and installs the
# spaCy model that keyphrase-vectorizers requires.
#
# The spaCy model is NOT a conda package, so it has to be downloaded
# separately. Skipping it makes every KeyBERT call raise OSError [E050].
set -euo pipefail

ENV_NAME="${ENV_NAME:-resume-ai}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v conda >/dev/null 2>&1; then
    echo "error: conda is not on PATH. Install Miniconda/Anaconda first." >&2
    exit 1
fi

echo "==> Creating conda env '${ENV_NAME}' (python 3.10)"
if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
    echo "    env already exists, skipping creation"
else
    conda create -y -n "${ENV_NAME}" python=3.10
fi

echo "==> Installing Python dependencies"
conda run -n "${ENV_NAME}" python -m pip install -r "${PROJECT_ROOT}/requirements.txt"

echo "==> Installing the spaCy model (en_core_web_sm)"
conda run -n "${ENV_NAME}" python -m spacy download en_core_web_sm

echo "==> Verifying the environment"
conda run -n "${ENV_NAME}" python -c "import spacy; spacy.load('en_core_web_sm'); print('    en_core_web_sm OK')"

echo
echo "Done. Activate with:  conda activate ${ENV_NAME}"
echo "Then run:             python -m pytest"
echo "                       python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
