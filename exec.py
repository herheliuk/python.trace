#!/usr/bin/env python3

from utils.context_managers import use_dir

import ast

from sys import argv, exit
from pathlib import Path
from copy import deepcopy

def exec_ast_segments(file_path: Path):
    source = file_path.read_text(encoding='utf-8')
    parsed_ast = ast.parse(source, filename=file_path.name)

    exec_globals = {'__file__': str(file_path)}

    def exec_node(node, local_vars=None):
        node_ast = ast.Module(body=[node], type_ignores=[])
        code_obj = compile(node_ast, filename=str(file_path), mode='exec', dont_inherit=True)
        exec(code_obj, exec_globals, local_vars or exec_globals)

    def detect_calls(node):
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                yield child

    def step_through_nodes(nodes, local_vars=None):
        for node in nodes:
            code_str = ast.unparse(node)
            input(f">>> {code_str}")
            exec_node(node, local_vars=local_vars)

            for call_node in detect_calls(node):
                func_name = None
                if isinstance(call_node.func, ast.Name):
                    func_name = call_node.func.id
                elif isinstance(call_node.func, ast.Attribute):
                    func_name = call_node.func.attr

                if func_name in exec_globals and callable(exec_globals[func_name]):
                    func_def = next(
                        (n for n in parsed_ast.body if isinstance(n, ast.FunctionDef) and n.name == func_name),
                        None
                    )
                    if func_def:
                        print(f"--- Stepping into {func_name} ---")

                        arg_values = [eval(ast.unparse(arg), exec_globals) for arg in call_node.args]
                        local_env = dict(zip([arg.arg for arg in func_def.args.args], arg_values))

                        body_copy = deepcopy(func_def.body)

                        for stmt in body_copy:
                            for n in ast.walk(stmt):
                                if isinstance(n, ast.Return):
                                    n.value = ast.Name(id='__return__', ctx=ast.Store()) if n.value is None else ast.Assign(
                                        targets=[ast.Name(id='__return__', ctx=ast.Store())],
                                        value=n.value
                                    )
                                    n.__class__ = ast.Pass

                        step_through_nodes(body_copy, local_vars=local_env)

                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                exec_globals[ast.unparse(target)] = local_env.get('__return__')

    step_through_nodes(parsed_ast.body)

if __name__ == "__main__":
    script = Path(argv[1]).resolve()
    with use_dir(script.parent):
        try:
            exec_ast_segments(script)
        except KeyboardInterrupt:
            exit(1)
