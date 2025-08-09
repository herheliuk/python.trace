#!/usr/bin/env python3

import os, sys
import runpy, linecache, json
from pathlib import Path

from ast_functions import find_python_imports

if len(sys.argv) != 2:
    print(f'Usage: python {sys.argv[0]} <script to debug>')
    sys.exit(1)

debug_script_path = Path(sys.argv[1]).resolve()

if not debug_script_path.exists():
    print(f'Error: File "{debug_script_path.name}" does not exist.')
    sys.exit(1)

paths_to_trace = find_python_imports(debug_script_path)
paths_to_trace = {str(file) for file in paths_to_trace}

this_script_dir = Path.cwd()
debug_script_dir = debug_script_path.parent
if not debug_script_dir in sys.path:
    sys.path.insert(0, str(debug_script_dir))
    os.chdir(debug_script_dir)
    
interactive = input('step through? ').strip()

if not interactive:
    output_file = this_script_dir / (debug_script_path.stem + '.trace.txt')
    print(f'writing to {output_file.name}...')
    sys.stdout = open(output_file, 'w')

def filter_scope(scope):
    return {key: value for key, value in scope.items() if not key.startswith("__")}

def trace_function(frame, event, arg):
    code_frame = frame.f_code
    code_filepath = code_frame.co_filename
    
    if code_filepath not in paths_to_trace:
        return

    code_name = code_frame.co_name
    filename = Path(code_filepath).name

    if code_name == '<module>':
        target = filename
        function_name = None
    else:
        target = code_name
        function_name = None if code_name.startswith('<') else code_name
    
    match event:
        case 'call':
            print(f"calling {target}\n")
            return trace_function

        case 'line':
            line_number = frame.f_lineno
            debug_data = json.dumps(
                {
                    'filename': filename,
                    f'line {{{line_number}}}': linecache.getline(code_filepath, line_number).strip(),
                    'globals': filter_scope(frame.f_globals),
                    **({
                        'function': function_name,
                        'locals': filter_scope(frame.f_locals)
                    } if function_name else {})
                },
                indent = 4,
                default = lambda obj: f"<{type(obj).__name__}>"
            ) + '\n'
            input(debug_data) if interactive else print(debug_data)
        
        case 'return':
            print(f"{target} returned {arg}\n")

try:
    sys.settrace(trace_function)
    runpy.run_path(debug_script_path)
finally:
    sys.settrace(None)
    if not interactive: 
        sys.stdout.close()
