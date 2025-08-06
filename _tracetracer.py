#!/usr/bin/env python3

import os, sys
import runpy, linecache, json
from pathlib import Path

from get_paths_to_trace import main as get_paths_to_trace

if len(sys.argv) != 2:
    print(f'Usage: python {sys.argv[0]} <script to debug>')
    sys.exit(1)

debug_script_path = Path(sys.argv[1]).resolve()

if not debug_script_path.exists():
    print(f'Error: File "{debug_script_path.name}" does not exist.')
    sys.exit(1)

script_dir = Path.cwd()
if not (debug_script_dir := debug_script_path.parent) in sys.path:
    sys.path.insert(0, str(debug_script_dir))
    os.chdir(debug_script_dir)

if not (interactive := input('step through? ').strip()):
    output_file = script_dir / (debug_script_path.stem + '.trace.txt')
    print(f'writing to {output_file.name}...')
    sys.stdout = open(output_file, 'w')

paths_to_trace = get_paths_to_trace(debug_script_path)

def filter_scope(scope):
    return {key: value for key, value in scope.items() if not key.startswith("__")}

def trace_function(frame, event, arg):
    code_frame = frame.f_code
    code_filename = code_frame.co_filename

    if code_filename not in paths_to_trace: return

    code_name = code_frame.co_name
    function_name = None if code_name == '<module>' else code_name
    
    match event:
        case 'call':
            if function_name:
                print(f"calling {function_name}")
            return trace_function
        case 'line':
            line_number = frame.f_lineno
            debug_data = json.dumps(
                {
                    'module': Path(code_filename).name,
                    f'line {line_number}': linecache.getline(code_filename, line_number).strip(),
                    'globals': filter_scope(frame.f_globals),
                    **({'locals': filter_scope(frame.f_locals)} if function_name else {})
                },
                indent = 4,
                default = lambda obj: f"<{type(obj).__name__}>"
            )
            input(debug_data) if interactive else print(debug_data)
        case 'return':
            if function_name:
                print(f"{function_name} returned{' ' + arg if arg else ''}")

try:
    sys.settrace(trace_function)
    runpy.run_path(debug_script_path)
finally:
    sys.settrace(None)
