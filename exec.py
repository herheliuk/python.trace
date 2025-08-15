#!/usr/bin/env python3

from utils.context_managers import use_dir
import ast
from sys import argv, exit
from pathlib import Path

def exec_ast_segments(file_path: Path):
    source = file_path.read_text(encoding='utf-8')
    parsed_ast = ast.parse(source, filename=file_path.name)

    exec_globals = {'__file__': str(file_path)}

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    def exec_node(node, local_vars=None):
        node_ast = ast.Module(body=[node], type_ignores=[])
        code_obj = compile(node_ast, filename=str(file_path), mode='exec', dont_inherit=True)
        exec(code_obj, exec_globals, local_vars or exec_globals)

    def step_through_nodes(nodes, local_vars=None):
        local_vars = local_vars or {}
        for node in nodes:
            code_str = ast.unparse(node)
            input(f">>> {code_str}")

            if isinstance(node, ast.FunctionDef):
                exec_node(node, exec_globals)
            elif isinstance(node, ast.Return):
                value = None
                if node.value:
                    value = eval_ast_expr(node.value, local_vars)
                raise ReturnValue(value)
            elif isinstance(node, ast.Expr):
                eval_ast_expr(node.value, local_vars)
            elif isinstance(node, ast.Assign):
                value = eval_ast_expr(node.value, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_vars[target.id] = value
                    else:
                        exec_node(ast.Assign(targets=[target], value=node.value), local_vars)
            else:
                exec_node(node, local_vars)

    def eval_ast_expr(node, local_vars):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
    
            arg_values = [eval_ast_expr(arg, local_vars) for arg in node.args]
    
            if func_name in exec_globals:
                func_obj = exec_globals[func_name]
                func_def = next((n for n in parsed_ast.body if isinstance(n, ast.FunctionDef) and n.name == func_name), None)
                if func_def:
                    print(f"--- Stepping into {func_name} ---")
                    func_local = dict(zip([arg.arg for arg in func_def.args.args], arg_values))
                    try:
                        step_through_nodes(func_def.body, func_local)
                        result = func_local.get('__return__')
                    except ReturnValue as r:
                        result = r.value
                    print(f"Function {func_name} returned {result}")
                    return result
                else:
                    result = func_obj(*arg_values)
                    print(f"Function {func_name} returned {result}")
                    return result
            else:
                result = eval(compile(ast.Expression(node), filename=str(file_path), mode='eval'), exec_globals, local_vars)
                return result
        elif isinstance(node, ast.Name):
            return local_vars.get(node.id, exec_globals.get(node.id))
        elif isinstance(node, ast.Constant):
            return node.value
        else:
            return eval(compile(ast.Expression(node), filename=str(file_path), mode='eval'), exec_globals, local_vars)

    step_through_nodes(parsed_ast.body)

if __name__ == "__main__":
    script = Path(argv[1]).resolve()
    with use_dir(script.parent):
        try:
            exec_ast_segments(script)
        except KeyboardInterrupt:
            exit(1)
