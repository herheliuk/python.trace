#!/usr/bin/env python3

import sys, os, io

from contextlib import contextmanager
from pathlib import Path

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
