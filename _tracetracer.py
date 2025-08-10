#!/usr/bin/env python3

import os, sys, runpy, json, io
from linecache import getline
from pathlib import Path
from contextlib import contextmanager
from functools import partial
from collections import defaultdict
from traceback import format_tb

from ast_functions import find_python_imports

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

def main(debug_script_path: Path, output_file: Path) -> None:
    paths_to_trace = {str(file) for file in find_python_imports(debug_script_path)}

    interactive = input('step through? ')
    
    if interactive:
        def log_step(data: str):
            print(data)
        def print_step(data: str):
            input(data)
    else:
        buffer = io.StringIO()
        def log_step(data: str):
            buffer.write(data)
        def print_step(data: str):
            buffer.write(data)
    
    last_scopes = defaultdict(dict)
        
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
            current_locals = {}
        else:
            target = code_name
            function_name = None if code_name.startswith('<') else code_name
            current_locals = dict(frame.f_locals)
            
        current_globals = dict(frame.f_globals)
            
        if event in ('line', 'return'):
            old_globals, old_locals = last_scopes[code_filepath][function_name]
                
            global_changes = diff_scope(old_globals, current_globals)
            local_changes = diff_scope(old_locals, current_locals) if function_name else {}
                
            if global_changes or local_changes:
                log_step(json_pretty({
                    'filename': filename,
                    **({'function': function_name} if function_name else {}),
                    **({'globals': global_changes} if global_changes else {}),
                    **({'locals': local_changes} if local_changes else {})
                }) + '\n')
                
            last_scopes[code_filepath][function_name] = (current_globals, current_locals)

        log_step(f"{f' {event} ':-^50}\n")
            
        if event == 'line':
            print_step(json_pretty({
                'filename': filename,
                **({'function': function_name} if function_name else {}),
                'line': frame.f_lineno,
                'code': getline(code_filepath, frame.f_lineno).strip()
            }) + '\n')
            return
            
        elif event == 'call':
            print_step(f"calling {target}\n")
            if not last_scopes[code_filepath].get(function_name, None):
                last_scopes[code_filepath][function_name] = (current_globals, current_locals)
                if current_locals:
                    log_step(json_pretty(current_locals) + '\n')
            return trace_function

        elif event == 'return':
            log_step(f"{target} returned {arg}\n")
            del last_scopes[code_filepath][function_name]
            return

        elif event == 'exception':
            exc_type, exc_value, exc_traceback = arg
            log_step(f"{exc_type.__name__}: {exc_value}\n")
            log_step(''.join(format_tb(exc_traceback)))
            return

    with apply_dir(debug_script_path.parent), apply_trace(trace_function):
        runpy.run_path(debug_script_path)

    last_scopes.clear()
    
    if not interactive:
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
    
    output_file = Path.cwd() / (debug_script_path.stem + '.trace.txt')
        
    main(debug_script_path, output_file)
