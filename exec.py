#!/usr/bin/env python3

from utils.context_managers import use_dir
import ast
import importlib
import inspect
from sys import argv, exit
from pathlib import Path


def exec_ast_segments(file_path: Path):
    assert file_path.name == 'test.py', 'this script is in dev!'

    all_func_defs = {}
    project_root = file_path.parent.resolve()
    module_scopes = {}  # Store globals of executed modules

    def is_project_file(path: Path) -> bool:
        return path.resolve().is_relative_to(project_root)

    def index_functions_from_file(path: Path):
        try:
            if not path.exists() or path.suffix != ".py":
                return
            if not is_project_file(path):
                return
            src = path.read_text(encoding="utf-8")
            parsed = ast.parse(src, filename=path.name)
            for node in parsed.body:
                if isinstance(node, ast.FunctionDef):
                    all_func_defs[node.name] = (node, path)
            return parsed
        except Exception as e:
            print(f"[WARN] Could not index functions from {path}: {e}")

    def step_execute_module(path: Path):
        """Step-execute a module and store its globals."""
        if path in module_scopes:
            return module_scopes[path]

        src = path.read_text(encoding="utf-8")
        parsed = ast.parse(src, filename=path.name)
        mod_globals = {'__file__': str(path)}

        print(f"\n--- Stepping through imported module: {path} ---")
        step_through_nodes(parsed.body, mod_globals)
        module_scopes[path] = mod_globals
        return mod_globals

    def index_from_imports(parsed_ast):
        for node in parsed_ast.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    try:
                        mod = importlib.import_module(alias.name)
                        mod_path = Path(inspect.getfile(mod))
                        if is_project_file(mod_path):
                            step_execute_module(mod_path)
                            index_functions_from_file(mod_path)
                    except Exception:
                        pass
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    try:
                        mod = importlib.import_module(node.module)
                        mod_path = Path(inspect.getfile(mod))
                        if is_project_file(mod_path):
                            step_execute_module(mod_path)
                            index_functions_from_file(mod_path)
                    except Exception:
                        pass

    parsed_ast = index_functions_from_file(file_path)
    if parsed_ast:
        index_from_imports(parsed_ast)

    exec_globals = {'__file__': str(file_path)}

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    def located(new_node, template):
        ast.copy_location(new_node, template)
        return ast.fix_missing_locations(new_node)

    def compile_stmt(node):
        mod = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(mod)
        return compile(mod, filename=str(file_path), mode='exec', dont_inherit=True)

    def compile_expr(node):
        expr_mod = ast.Expression(node)
        ast.fix_missing_locations(expr_mod)
        return compile(expr_mod, filename=str(file_path), mode='eval', dont_inherit=True)

    def exec_node(node, local_vars=None):
        code_obj = compile_stmt(node)
        exec(code_obj, exec_globals, local_vars or exec_globals)

    def eval_ast_expr(node, local_vars):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            arg_values = [eval_ast_expr(arg, local_vars) for arg in node.args]

            if func_name in all_func_defs:
                func_def, def_path = all_func_defs[func_name]
                exec_scope = module_scopes.get(def_path, exec_globals)
                func_local = dict(zip([arg.arg for arg in func_def.args.args], arg_values))
                try:
                    step_through_nodes(func_def.body, func_local)
                    result = func_local.get('__return__')
                except ReturnValue as r:
                    result = r.value
                print(f"Function {func_name} returned {result}")
                return result

            elif func_name in exec_globals:
                func_obj = exec_globals[func_name]
                result = func_obj(*arg_values)
                print(f"Function {func_name} returned {result}")
                return result
            else:
                return eval(compile_expr(node), exec_globals, local_vars)

        elif isinstance(node, ast.Name):
            if node.id in local_vars:
                return local_vars[node.id]
            return exec_globals.get(node.id)
        elif isinstance(node, ast.Constant):
            return node.value
        else:
            return eval(compile_expr(node), exec_globals, local_vars)

    def step_through_nodes(nodes, local_vars=None):
        local_vars = local_vars or {}
        for node in nodes:
            code_str = ast.unparse(node)
            print(f">>> {code_str}") if len(argv) == 3 else input(f">>> {code_str}")

            if isinstance(node, ast.FunctionDef):
                exec_node(node, local_vars)
            elif isinstance(node, ast.ClassDef):
                exec_node(node, local_vars)
            elif isinstance(node, ast.Return):
                value = eval_ast_expr(node.value, local_vars) if node.value else None
                raise ReturnValue(value)
            elif isinstance(node, ast.Expr):
                eval_ast_expr(node.value, local_vars)
            elif isinstance(node, ast.Assign):
                value = eval_ast_expr(node.value, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_vars[target.id] = value
                    else:
                        assign_node = located(ast.Assign(targets=[target], value=node.value), node)
                        exec_node(assign_node, local_vars)
            elif isinstance(node, ast.For):
                iter_obj = eval_ast_expr(node.iter, local_vars)
                for item in iter_obj:
                    if isinstance(node.target, ast.Name):
                        local_vars[node.target.id] = item
                    else:
                        assign_node = located(
                            ast.Assign(targets=[node.target], value=ast.Constant(item)),
                            node
                        )
                        exec_node(assign_node, local_vars)
                    step_through_nodes(node.body, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.While):
                while eval_ast_expr(node.test, local_vars):
                    step_through_nodes(node.body, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.If):
                if eval_ast_expr(node.test, local_vars):
                    step_through_nodes(node.body, local_vars)
                else:
                    step_through_nodes(node.orelse, local_vars)
            elif isinstance(node, ast.With):
                managers = []
                for item in node.items:
                    context = eval_ast_expr(item.context_expr, local_vars)
                    enter = getattr(context, "__enter__", None)
                    exit_ = getattr(context, "__exit__", None)
                    if enter is None or exit_ is None:
                        raise RuntimeError(f"Object {context} is not a context manager")
                    value = enter()
                    varname = (
                        item.optional_vars.id
                        if item.optional_vars and isinstance(item.optional_vars, ast.Name)
                        else None
                    )
                    if varname:
                        local_vars[varname] = value
                    managers.append(exit_)
                try:
                    step_through_nodes(node.body, local_vars)
                finally:
                    for exit_ in reversed(managers):
                        exit_(None, None, None)
            elif isinstance(node, ast.Try):
                try:
                    step_through_nodes(node.body, local_vars)
                except Exception as e:
                    handled = False
                    for handler in node.handlers:
                        if handler.type is None:
                            step_through_nodes(handler.body, local_vars)
                            handled = True
                            break
                        try:
                            exc_type = eval_ast_expr(handler.type, local_vars)
                            if isinstance(e, exc_type):
                                step_through_nodes(handler.body, local_vars)
                                handled = True
                                break
                        except Exception:
                            pass
                    if not handled:
                        raise
                finally:
                    step_through_nodes(node.finalbody, local_vars)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars)
            else:
                exec_node(node, local_vars)

    step_through_nodes(parsed_ast.body)


if __name__ == "__main__":
    script = Path(argv[1]).resolve()
    with use_dir(script.parent):
        try:
            exec_ast_segments(script)
        except KeyboardInterrupt:
            exit(1)
