#!/usr/bin/env python3

import os, sys, runpy, linecache, json, io
from pathlib import Path
from functools import partial
from collections import defaultdict

from ast_functions import find_python_imports

getline = linecache.getline

def default_json_handler(obj):
    typename = type(obj).__name__
    return f"<{typename}>"

json_pretty = partial(json.dumps, indent=4, default=default_json_handler)

def filter_scope(scope: dict) -> dict:
    startswith = str.startswith
    return {key: value for key, value in scope.items() if not startswith(key, "__")}

def diff_scope(old_scope: dict, new_scope: dict) -> dict:
    changes = {key: value for key, value in new_scope.items() if old_scope.get(key) != value}
    deleted = {key: "<deleted>" for key in old_scope.keys() - new_scope.keys()}
    return {**changes, **deleted}

def main(debug_script_path):
    paths_to_trace = {str(file) for file in find_python_imports(debug_script_path)}

    this_script_dir = Path.cwd()
    debug_script_dir = debug_script_path.parent
    if not debug_script_dir in sys.path:
        sys.path.insert(0, str(debug_script_dir))
        os.chdir(debug_script_dir)

    interactive = input('step through? ').strip()

    if not interactive:
        output_file = this_script_dir / (debug_script_path.stem + '.trace.txt')
        print(f'writing to {output_file.name}...')
        buffer = io.StringIO()
        sys.stdout = buffer

    try:
        last_scopes = defaultdict(lambda: defaultdict(lambda: ({}, {})))

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
            
            if event in ('line', 'return'):
                cur_globals = dict(frame.f_globals)
                cur_locals = dict(frame.f_locals) if function_name else {}
                 
                old_globals, old_locals = last_scopes[code_filepath].get(function_name, ({}, {}))
                
                global_changes = diff_scope(old_globals, cur_globals)
                local_changes = diff_scope(old_locals, cur_locals) if function_name else {}
                
                last_scopes[code_filepath][function_name] = (cur_globals, cur_locals)
                
                if global_changes or local_changes:
                    print(json_pretty({
                        'filename': filename,
                        **({'function': function_name} if function_name else {}),
                        **({'globals': global_changes} if filter_scope(global_changes) else {}),
                        **({'locals': local_changes} if filter_scope(local_changes) else {})
                    }) + '\n')

            print(f"{f' {event} ':*^50}\n")
            
            if event == 'call':
                message = f"calling {target}\n"
                input(message) if interactive else print(message)
                if not last_scopes[code_filepath].get(function_name, None):
                    cur_globals = dict(frame.f_globals)
                    cur_locals = dict(frame.f_locals) if function_name else {}
                    last_scopes[code_filepath][function_name] = (cur_globals, cur_locals)
                return trace_function
            
            elif event == 'line':
                message = json_pretty({
                    'filename': filename,
                    **({'function': function_name} if function_name else {}),
                    f'line {{{frame.f_lineno}}}': getline(code_filepath, frame.f_lineno).strip()
                }) + '\n'
                input(message) if interactive else print(message)

            elif event == 'return':
                print(f"{target} returned {arg}\n")
                del last_scopes[code_filepath][function_name]

        sys.settrace(trace_function)
        runpy.run_path(debug_script_path)
    finally:
        last_scopes.clear()
        sys.settrace(None)
        if not interactive:
            sys.stdout = sys.__stdout__
            output_file.write_bytes(buffer.getvalue().encode('utf-8'))
            buffer.close()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <script to debug>')
        sys.exit(1)

    debug_script_path = Path(sys.argv[1]).resolve()

    if not debug_script_path.exists():
        print(f'Error: File "{debug_script_path.name}" does not exist.')
        sys.exit(1)
        
    main(debug_script_path)
