#!/bin/bash

[[ "${BASH_SOURCE[0]}" == "${0}" ]] && {
    echo "Please use 'source' or '.' to run env.sh."
}

if [[ "$(uname)" != "Darwin" ]]; then
    python3 -m venv --help >/dev/null 2>&1 || {
        echo "Installing python3-venv..."
        sudo apt install -y python3-venv
    }
fi

[ ! -d env ] && {
    echo "Creating virtual environment..."
    python3 -m venv env
    
    echo "Activating virtual environment..."
    source env/bin/activate

    [ -f requirements.txt ] && {
        echo "Installing requirements..."
        pip install -r requirements.txt
    }
}

[ -z "$VIRTUAL_ENV" ] && {
    echo "Activating virtual environment..."
    source env/bin/activate
}
