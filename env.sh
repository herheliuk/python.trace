#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Please use 'source' or '.' to run $(basename "$0")."
    return 1
fi

if [[ "$(uname)" != "Darwin" ]] && ! python3 -m venv --help &>/dev/null; then
    echo "Installing python3-venv..."
    sudo apt update && sudo apt install -y python3-venv
fi

if [[ ! -d env ]]; then
    echo "Creating virtual environment..."
    python3 -m venv env
fi

if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Activating virtual environment..."
    source env/bin/activate
fi

if [[ -f requirements.txt ]]; then
    echo "Installing requirements..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi
