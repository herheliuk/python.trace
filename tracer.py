#!/usr/bin/env python3

import os, sys, runpy, linecache, json, io
from pathlib import Path
from functools import partial

from ast_functions import find_python_imports

# ------------------------
# Parse args
# ------------------------
if len(sys.argv) != 2:
    print(f'Usage: python {sys.argv[0]} <script to debug>')
    sys.exit(1)

debug_script_path = Path(sys.argv[1]).resolve()

if not debug_script_path.exists():
    print(f'Error: File "{debug_script_path.name}" does not exist.')
    sys.exit(1)

# ------------------------
# Precompute imports paths
# ------------------------
paths_to_trace = {str(Path(file).resolve()) for file in find_python_imports(debug_script_path)}

this_script_dir = Path.cwd()
debug_script_dir = debug_script_path.parent
if debug_script_dir not in sys.path:
    sys.path.insert(0, str(debug_script_dir))
    os.chdir(debug_script_dir)

interactive = input('step through? ').strip()

# Output buffering if non-interactive
if not interactive:
    output_file = this_script_dir / (debug_script_path.stem + '.trace.txt')
    print(f'writing to {output_file.name}...')
    buffer = io.StringIO()
    sys.stdout = buffer

# ------------------------
# Helpers
# ------------------------
filter_scope = lambda scope: {k: v for k, v in scope.items() if not k.startswith("__")}
json_pretty = partial(json.dumps, indent=4, default=lambda o: f"<{type(o).__name__}>")
getline = linecache.getline

def diff_scope(old, new):
    changes = {}
    for k, v in new.items():
        if k not in old or old[k] != v:
            changes[k] = v
    for k in old.keys() - new.keys():
        changes[k] = "<deleted>"
    return changes

last_scopes = {}
last_lines = {}

# ------------------------
# Trace function
# ------------------------
def trace_function(frame, event, arg):
    code_filepath = frame.f_code.co_filename
    if code_filepath not in paths_to_trace:
        return

    filename = Path(code_filepath).name
    code_name = frame.f_code.co_name
    function_name = None if code_name.startswith('<') else code_name

    if event in ('line', 'return'):
        # Skip reprocessing unchanged lines
        prev_line = last_lines.get(code_filepath)
        if prev_line == frame.f_lineno and event == 'line':
            return
        last_lines[code_filepath] = frame.f_lineno

        cur_globals = filter_scope(frame.f_globals)
        cur_locals = filter_scope(frame.f_locals) if function_name else {}

        old_globals, old_locals = last_scopes.get(code_filepath, ({}, {}))
        global_changes = diff_scope(old_globals, cur_globals)
        local_changes = diff_scope(old_locals, cur_locals) if function_name else {}

        if global_changes or local_changes:
            print(json_pretty({
                'filename': filename,
                **({'function': function_name} if function_name else {}),
                **({'new globals': global_changes} if global_changes else {}),
                **({'new locals': local_changes} if local_changes else {})
            }))

        last_scopes[code_filepath] = (cur_globals, cur_locals)

    if event == 'call':
        msg = f"calling {function_name or filename}\n"
        input(msg) if interactive else print(msg, end="")
        return trace_function

    elif event == 'line':
        msg = json_pretty({
            'filename': filename,
            **({'function': function_name} if function_name else {}),
            f'line {{{frame.f_lineno}}}': getline(code_filepath, frame.f_lineno).strip()
        }) + '\n'
        input(msg) if interactive else print(msg, end="")

    elif event == 'return':
        print(f"{function_name or filename} returned {arg}\n")
        if code_name == '<module>':
            last_scopes.pop(code_filepath, None)

# ------------------------
# Run script with trace
# ------------------------
try:
    sys.settrace(trace_function)
    runpy.run_path(debug_script_path)
finally:
    sys.settrace(None)
    if not interactive:
        sys.stdout = sys.__stdout__
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(buffer.getvalue())
        buffer.close()
