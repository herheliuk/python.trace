#!/usr/bin/env python3

from io import StringIO
from sys import path, gettrace, settrace
from os import chdir
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def apply_dir(target_dir: Path):
    original_dir = Path.cwd()
    target_dir = str(target_dir)
    if target_dir not in path:
        path.insert(0, target_dir)
        chdir(target_dir)
    try:
        yield
    finally:
        if target_dir in path:
            path.remove(target_dir)
            chdir(original_dir)
    
@contextmanager
def apply_trace(trace_function):
    old_trace = gettrace()
    settrace(trace_function)
    try:
        yield
    finally:
        settrace(old_trace)

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
        buffer = StringIO()
        
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
