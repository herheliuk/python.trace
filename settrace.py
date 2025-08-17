#!/usr/bin/env python3

from utils.ast_functions import find_python_imports, get_source_code_cache
from utils.context_managers import use_dir, use_trace, step_io
from utils.scope_functions import diff_scope, filter_scope

from json import dumps
from sys import argv, exit
from pathlib import Path
from collections import defaultdict
from functools import partial
from traceback import format_tb

def default_json_handler(obj):
    return f"<{type(obj).__name__}>"

pretty_json = partial(dumps, indent=4, default=default_json_handler)

def main(debug_script_path: Path, output_file: Path, interactive = None):
    paths_to_trace = find_python_imports(debug_script_path)
    
    source_code_cache = {
        str(path): get_source_code_cache(path)
        for path in paths_to_trace
    }
    
    last_files = defaultdict(dict)
    
    str_paths_to_trace = {
        str(path)
        for path in paths_to_trace
    }
    
    def revert_line():
        ...
    
    def jump_line(lineno):
        ...
    
    with step_io(output_file, interactive, jump_line, revert_line) as (print_step, input_step):
        def trace_function(frame, event, arg):
            str_code_filepath = frame.f_code.co_filename
            if str_code_filepath not in str_paths_to_trace: return

            code_name = frame.f_code.co_name
            filename = Path(str_code_filepath).name

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

            last_functions = last_files[str_code_filepath]

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
                    print_step(pretty_json(payload))

            print_step(f"{f' {event} ':-^50}")

            if event == 'line':
                input_step(pretty_json({
                    'filename': filename,
                    **({'function': function_name} if function_name else {}),
                    'lineno': frame.f_lineno,
                    **(source_code_cache[str_code_filepath][frame.f_lineno])
                }))
                last_functions[function_name] = current_globals, current_locals
                return

            elif event == 'call':
                input_step(f"calling {target}")
                if current_locals: print_step(pretty_json(current_locals))
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
        
        source_code = debug_script_path.read_text()
        
        compiled = compile(
            source_code,
            filename=debug_script_path,
            mode='exec',
            dont_inherit=True
        )
        
        exec_globals = {
            '__file__': str(debug_script_path)
        }
        
        with use_dir(debug_script_path.parent), use_trace(trace_function):
            try:
                exec(
                    compiled,
                    globals=exec_globals,
                    locals=None
                )
            except KeyboardInterrupt:
                print()
                exit(1)

def erase_last_line_from_terminal():
    print("\033[F\033[K", end='', flush=True)

if __name__ == '__main__':
    if len(argv) != 2:
        print(f'Usage: python {argv[0]} <script to debug>')
        exit(1)

    debug_script_path = Path(argv[1]).resolve()
    
    if not debug_script_path.is_file():
        print(f'Error: File "{debug_script_path.name}" does not exist or is a directory.')
        exit(1)
        
    interactive = input('Step through? '); erase_last_line_from_terminal()
    
    output_file = Path.cwd() / (debug_script_path.stem + '.trace.txt')
        
    main(debug_script_path, output_file, interactive)
