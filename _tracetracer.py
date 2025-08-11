#!/usr/bin/env python3

from ast_functions import find_python_imports

import os, sys, runpy, json, io
from linecache import getlines
from pathlib import Path
from contextlib import contextmanager
from functools import partial
from collections import defaultdict
from traceback import format_tb

@contextmanager
def apply_dir(target_dir: Path):
    original_dir = Path.cwd()
    target_dir = str(target_dir)
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)
        os.chdir(target_dir)
    try:
        yield
    finally:
        if target_dir in sys.path:
            sys.path.remove(target_dir)
            os.chdir(original_dir)
    
@contextmanager
def apply_trace(trace_function):
    old_trace = sys.gettrace()
    sys.settrace(trace_function)
    try:
        yield
    finally:
        sys.settrace(old_trace)

@contextmanager
def step_io(output_file: Path, interactive: bool):
    if interactive:
        def print_step(text):
            print(text)
            
        def input_step(text):
            return input(text)
        
        def finalize():
            pass
    else:
        buffer = io.StringIO()
        
        def print_step(text):
            buffer.write(text + '\n')
            
        def input_step(text):
            buffer.write(text + '\n')
            
        def finalize():
            output_file.write_bytes(buffer.getvalue().encode('utf-8'))
            buffer.close()

    try:
        yield print_step, input_step
    finally:
        finalize()
        
def default_json_handler(obj):
    typename = type(obj).__name__
    return f"<{typename}>"

json_pretty = partial(json.dumps, indent=4, default=default_json_handler)

def filter_scope(scope):
    startswith = str.startswith
    return {key: value for key, value in scope.items() if not startswith(key, "__")}

def diff_scope(old_scope: dict, new_scope: dict):
    if old_scope is new_scope:
        return {}
    changes = {key: value for key, value in new_scope.items() if old_scope.get(key) != value}
    deleted = {key: "<deleted>" for key in old_scope.keys() - new_scope.keys()}
    return {**changes, **deleted}

def main(debug_script_path: Path, output_file: Path, interactive = None):
    paths_to_trace = {str(file) for file in find_python_imports(debug_script_path)}
    source_cache = {path: getlines(path) for path in paths_to_trace}
    last_files = defaultdict(dict)
    
    with step_io(output_file, interactive) as (print_step, input_step):
        def trace_function(frame, event, arg):
            code_filepath = frame.f_code.co_filename
            if code_filepath not in paths_to_trace:
                return

            code_name = frame.f_code.co_name
            filename = Path(code_filepath).name

            is_not_module = code_name != '<module>'

            if is_not_module:
                target = code_name
                function_name = None if code_name.startswith('<') else code_name
                current_locals = dict(frame.f_locals)
            else:
                target = filename
                function_name = None
                current_locals = {}

            current_globals = dict(frame.f_globals)

            last_functions = last_files[code_filepath]

            if event in ('line', 'return'):
                old_globals, old_locals = last_functions[function_name]

                global_changes = diff_scope(old_globals, current_globals)
                local_changes = diff_scope(old_locals, current_locals) if is_not_module else {}

                if global_changes or local_changes:
                    payload = {'filename': filename}
                    if function_name:
                        payload['function'] = function_name
                    if global_changes:
                        payload['globals'] = global_changes
                    if local_changes:
                        payload['locals'] = local_changes
                    print_step(json_pretty(payload))

            print_step(f"{f' {event} ':-^50}")

            if event == 'line':
                input_step(json_pretty({
                    'filename': filename,
                    **({'function': function_name} if function_name else {}),
                    'line': frame.f_lineno,
                    'code': source_cache[code_filepath][frame.f_lineno - 1].strip()
                }))
                last_functions[function_name] = (current_globals, current_locals)
                return

            elif event == 'call':
                input_step(f"calling {target}")
                if current_locals:
                    print_step(json_pretty(current_locals))
                last_functions.setdefault(function_name, (current_globals, current_locals))
                return trace_function

            elif event == 'return':
                print_step(f"{target} returned {arg}")
                del last_functions[function_name]
                return

            elif event == 'exception':
                exc_type, exc_value, exc_traceback = arg
                print_step(f"{exc_type.__name__}: {exc_value}")
                print_step(''.join(format_tb(exc_traceback)))
                return

        with apply_dir(debug_script_path.parent), apply_trace(trace_function):
            try:
                runpy.run_path(debug_script_path)
            except KeyboardInterrupt:
                sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <script to debug>')
        sys.exit(1)

    debug_script_path = Path(sys.argv[1]).resolve()

    if not debug_script_path.exists():
        print(f'Error: File "{debug_script_path.name}" does not exist.')
        sys.exit(1)
        
    interactive = input('Step through? ')
    
    output_file = Path.cwd() / (debug_script_path.stem + '.trace.txt')
        
    main(debug_script_path, output_file, interactive)
