import ast
import inspect
import sys
from pathlib import Path

def stepper(file_path: Path, debug=False):
    PROJECT_ROOT = file_path.parent.resolve()

    exec_globals = {
        '__file__': str(file_path),
        '__name__': '__main__'
    }

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    # ---------- helpers ----------
    def located(new_node, template):
        ast.copy_location(new_node, template)
        return ast.fix_missing_locations(new_node)

    def compile_stmt(node, filename):
        mod = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(mod)
        return compile(mod, filename=str(filename), mode='exec')

    def compile_expr(node, filename):
        expr_mod = ast.Expression(node)
        ast.fix_missing_locations(expr_mod)
        return compile(expr_mod, filename=str(filename), mode='eval')

    def is_user_path(p: Path | None) -> bool:
        if p is None:
            return False
        try:
            p = Path(p).resolve()
        except Exception:
            return False
        # inside project, not inside site-packages, and not stdlib/venv prefix
        in_project = False
        try:
            p.relative_to(PROJECT_ROOT)
            in_project = True
        except ValueError:
            in_project = False
        return in_project and ("site-packages" not in str(p)) and (not str(p).startswith(sys.prefix))

    def print_line(s: str, depth: int):
        indent = "    " * depth
        print(f"{indent}{s}")

    # ---------- core exec/eval ----------
    def exec_node(node, local_vars=None, globals_dict=None, filename=None):
        g = exec_globals if globals_dict is None else globals_dict
        fname = file_path if filename is None else filename
        code_obj = compile_stmt(node, fname)
        if local_vars is None:
            exec(code_obj, g)
        else:
            exec(code_obj, g, local_vars)

    def eval_ast_expr(node, local_vars=None, globals_dict=None, filename=None, depth=0):
        g = exec_globals if globals_dict is None else globals_dict
        fname = file_path if filename is None else filename

        # merged scope for eval (fix for generators/comprehensions)
        def merged_scope():
            merged = dict(g)
            if local_vars:
                merged.update(local_vars)
            return merged

        def evaluate(node_):
            return eval(compile_expr(node_, fname), merged_scope())

        # -------- stepping into functions/classes --------
        def step_user_function(callable_obj, args_vals, kwargs_vals):
            if inspect.ismethod(callable_obj) and callable_obj.__self__ is not None:
                bound_self = callable_obj.__self__
                actual_func = callable_obj.__func__
            else:
                bound_self = None
                actual_func = callable_obj

            try:
                src_file = Path(inspect.getsourcefile(actual_func)).resolve()
                src_snippet = inspect.getsource(actual_func)
                src_start_lineno = inspect.getsourcelines(actual_func)[1]
                snippet_ast = ast.parse(src_snippet, filename=str(src_file))
                func_node = snippet_ast.body[0]
            except Exception:
                return callable_obj(*args_vals, **kwargs_vals)

            try:
                sig = inspect.signature(actual_func)
                bind_args = [bound_self] + list(args_vals) if bound_self else list(args_vals)
                ba = sig.bind_partial(*bind_args, **kwargs_vals)
                ba.apply_defaults()
                local_vars_func = dict(ba.arguments)
            except Exception:
                return callable_obj(*args_vals, **kwargs_vals)

            try:
                if actual_func.__closure__:
                    for name, cell in zip(actual_func.__code__.co_freevars, actual_func.__closure__):
                        if name not in local_vars_func:
                            try:
                                local_vars_func[name] = cell.cell_contents
                            except Exception:
                                pass
            except Exception:
                pass

            rel = str(src_file.relative_to(PROJECT_ROOT)) if is_user_path(src_file) else str(src_file)
            print_line(f"--> stepping into function {actual_func.__name__} ({rel}:{src_start_lineno})", depth)

            try:
                step_through_nodes(func_node.body,
                                   local_vars=local_vars_func,
                                   globals_dict=actual_func.__globals__,
                                   filename=src_file,
                                   depth=depth+1)
            except ReturnValue as rv:
                return rv.value
            return None

        def is_user_function_or_method(obj):
            if inspect.ismethod(obj):
                f = obj.__func__
            else:
                f = obj
            try:
                src = inspect.getsourcefile(f)
            except Exception:
                return False
            return inspect.isfunction(f) and is_user_path(Path(src) if src else None)

        def is_user_class(cls):
            try:
                src = inspect.getsourcefile(cls)
            except Exception:
                return False
            return inspect.isclass(cls) and is_user_path(Path(src) if src else None)

        def maybe_step_class_call(cls_obj, args_vals, kwargs_vals):
            try:
                src_file = Path(inspect.getsourcefile(cls_obj))
            except Exception:
                src_file = None

            instance = None
            # __new__
            try:
                new_callable = cls_obj.__new__
                new_for_check = new_callable.__func__ if inspect.ismethod(new_callable) else new_callable
                new_src = inspect.getsourcefile(new_for_check) if (inspect.isfunction(new_for_check) or inspect.ismethod(new_callable)) else None
                if new_src and is_user_path(Path(new_src)):
                    print_line(f"--> stepping into {cls_obj.__name__}.__new__", depth)
                    instance = step_user_function(new_callable, [cls_obj] + list(args_vals), kwargs_vals)
            except Exception:
                instance = None

            if instance is None:
                try:
                    instance = cls_obj.__new__(cls_obj, *args_vals, **kwargs_vals)
                except TypeError:
                    instance = object.__new__(cls_obj)

            # __init__
            try:
                init_callable = cls_obj.__init__
                init_for_check = init_callable.__func__ if inspect.ismethod(init_callable) else init_callable
                init_src = inspect.getsourcefile(init_for_check) if (inspect.isfunction(init_for_check) or inspect.ismethod(init_callable)) else None
                if init_src and is_user_path(Path(init_src)):
                    print_line(f"--> stepping into {cls_obj.__name__}.__init__", depth)
                    bound_init = instance.__init__
                    step_user_function(bound_init, list(args_vals), kwargs_vals)
                    return instance
            except Exception:
                pass

            cls_obj.__init__(instance, *args_vals, **kwargs_vals)
            return instance

        # -------- main node handling --------
        if isinstance(node, ast.Call):
            func_obj = evaluate(node.func)
            args_vals = [eval_ast_expr(arg, local_vars, g, fname, depth) for arg in node.args]
            kwargs_vals = {kw.arg: eval_ast_expr(kw.value, local_vars, g, fname, depth) for kw in node.keywords}

            if (inspect.isfunction(func_obj) or inspect.ismethod(func_obj)) and is_user_function_or_method(func_obj):
                return step_user_function(func_obj, args_vals, kwargs_vals)

            if inspect.isclass(func_obj) and (is_user_class(func_obj) or
                                             is_user_function_or_method(getattr(func_obj, '__init__', lambda: None)) or
                                             is_user_function_or_method(getattr(func_obj, '__new__', lambda: None))):
                return maybe_step_class_call(func_obj, args_vals, kwargs_vals)

            return func_obj(*args_vals, **kwargs_vals)

        elif isinstance(node, ast.Name):
            if local_vars is not None and node.id in local_vars:
                return local_vars[node.id]
            return g.get(node.id)

        elif isinstance(node, ast.Constant):
            return node.value

        else:
            return eval(compile_expr(node, fname), merged_scope())

    # ---------- stepping through nodes ----------
    def step_through_nodes(nodes, local_vars=None, globals_dict=None, filename=None, depth=0):
        g = exec_globals if globals_dict is None else globals_dict
        fname = file_path if filename is None else filename

        for node in nodes:
            try:
                code_line = ast.unparse(node)
            except Exception:
                code_line = type(node).__name__
            if debug:
                input(f"{'    '*depth}\033[1;35m>>> \033[1;30m{code_line}\033[0m")
            else:
                print(f"{'    '*depth}\033[1;35m>>> \033[1;30m{code_line}\033[0m")

            if isinstance(node, ast.FunctionDef):
                exec_node(node, local_vars, g, fname)
            elif isinstance(node, ast.ClassDef):
                exec_node(node, local_vars, g, fname)
            elif isinstance(node, ast.Return):
                value = eval_ast_expr(node.value, local_vars, g, fname, depth) if node.value else None
                raise ReturnValue(value)
            elif isinstance(node, ast.Expr):
                eval_ast_expr(node.value, local_vars, g, fname, depth)
            elif isinstance(node, ast.Assign):
                value = eval_ast_expr(node.value, local_vars, g, fname, depth)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        (local_vars or g)[target.id] = value
                    else:
                        assign_node = located(ast.Assign(targets=[target], value=node.value), node)
                        exec_node(assign_node, local_vars, g, fname)
            elif isinstance(node, ast.For):
                for item in eval_ast_expr(node.iter, local_vars, g, fname, depth):
                    if isinstance(node.target, ast.Name):
                        (local_vars or g)[node.target.id] = item
                    else:
                        assign_node = located(ast.Assign(targets=[node.target], value=ast.Constant(item)), node)
                        exec_node(assign_node, local_vars, g, fname)
                    step_through_nodes(node.body, local_vars, g, fname, depth)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars, g, fname, depth)
            elif isinstance(node, ast.While):
                while eval_ast_expr(node.test, local_vars, g, fname, depth):
                    step_through_nodes(node.body, local_vars, g, fname, depth)
                if node.orelse:
                    step_through_nodes(node.orelse, local_vars, g, fname, depth)
            elif isinstance(node, ast.If):
                if eval_ast_expr(node.test, local_vars, g, fname, depth):
                    step_through_nodes(node.body, local_vars, g, fname, depth)
                else:
                    step_through_nodes(node.orelse, local_vars, g, fname, depth)
            elif isinstance(node, ast.With):
                managers = []
                for item in node.items:
                    context = eval_ast_expr(item.context_expr, local_vars, g, fname, depth)
                    value = context.__enter__()
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        (local_vars or g)[item.optional_vars.id] = value
                    managers.append(context.__exit__)
                try:
                    step_through_nodes(node.body, local_vars, g, fname, depth)
                finally:
                    for exit_ in reversed(managers):
                        exit_(None, None, None)
            elif isinstance(node, ast.Try):
                try:
                    step_through_nodes(node.body, local_vars, g, fname, depth)
                except ReturnValue:
                    try:
                        step_through_nodes(node.finalbody, local_vars, g, fname, depth)
                    finally:
                        raise
                except Exception as e:
                    handled = False
                    for handler in node.handlers:
                        if handler.type is None or isinstance(e, eval_ast_expr(handler.type, local_vars, g, fname, depth)):
                            local_map = local_vars if local_vars is not None else g
                            if handler.name:
                                local_map[handler.name] = e
                            step_through_nodes(handler.body, local_vars, g, fname, depth)
                            handled = True
                            break
                    if not handled:
                        raise
                    step_through_nodes(node.finalbody, local_vars, g, fname, depth)
                else:
                    if node.orelse:
                        step_through_nodes(node.orelse, local_vars, g, fname, depth)
                    step_through_nodes(node.finalbody, local_vars, g, fname, depth)
            else:
                exec_node(node, local_vars, g, fname)

    # ---------- entry ----------
    src = file_path.read_text(encoding="utf-8")
    parsed_ast = ast.parse(src, filename=file_path.name)
    step_through_nodes(parsed_ast.body, local_vars=None, globals_dict=exec_globals, filename=file_path, depth=0)


if __name__ == '__main__':
    from settrace import use_dir, argv
    script_path = Path(argv[1]).resolve()
    assert script_path.name == 'test.py', 'this script is in dev!'
    with use_dir(script_path.parent):
        stepper(script_path, debug=len(argv) != 3)
