import ast
import types
from pathlib import Path

def stepper(file_path: Path, exec_globals=None, module_name=None):
    module_name = module_name or '__main__'
    exec_globals = exec_globals or {'__file__': str(file_path), '__name__': module_name}

    class ReturnValue(Exception):
        def __init__(self, value):
            self.value = value

    def located(new_node, template):
        ast.copy_location(new_node, template)
        return ast.fix_missing_locations(new_node)

    def compile_node(node, mode='exec'):
        if mode == 'exec':
            mod = ast.Module(body=[node], type_ignores=[])
        else:
            mod = ast.Expression(node)
        ast.fix_missing_locations(mod)
        return compile(mod, filename=str(file_path), mode=mode)

    def exec_node(node, local_vars=None):
        exec(compile_node(node, 'exec'), exec_globals, local_vars)

    def eval_node(node, local_vars=None):
        scope = exec_globals if local_vars is None else local_vars
        if isinstance(node, ast.Name):
            if local_vars and node.id in local_vars:
                return local_vars[node.id]
            return exec_globals.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        return eval(compile_node(node, 'eval'), exec_globals, scope)

    def step_nodes(nodes, local_vars=None):
        for node in nodes:
            if len(argv) >= 4: print(f'\033[32m{pretty_json(filter_scope(local_vars))}\033[1;37m')
            (print if len(argv) >= 3 else input)(f"\033[1;31m>>> \033[33m{ast.unparse(node)}\033[1;37m")

            # Problematic, returns from imported functions are raised instead.

#            if isinstance(node, ast.FunctionDef):
#                def make_func(node):
#                    arg_names = [arg.arg for arg in node.args.args]
#                    def func(*args, **kwargs):
#                        local_vars = dict(zip(arg_names, args))
#                        local_vars.update(kwargs)
#                        step_nodes(node.body, local_vars)
#                    return func
#            
#                func_obj = make_func(node)
#                (local_vars or exec_globals)[node.name] = func_obj

            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                exec_node(node, local_vars)

            elif isinstance(node, ast.Return):
                value = eval_node(node.value, local_vars) if node.value else None
                raise ReturnValue(value)

            elif isinstance(node, ast.Expr):
                eval_node(node.value, local_vars)

            elif isinstance(node, ast.Assign):
                value = eval_node(node.value, local_vars)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        (local_vars or exec_globals)[target.id] = value
                    else:
                        exec_node(located(ast.Assign(targets=[target], value=node.value), node), local_vars)

            elif isinstance(node, ast.For):
                for item in eval_node(node.iter, local_vars):
                    if isinstance(node.target, ast.Name):
                        (local_vars or exec_globals)[node.target.id] = item
                    else:
                        exec_node(located(ast.Assign(targets=[node.target], value=ast.Constant(item)), node), local_vars)
                    step_nodes(node.body, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            elif isinstance(node, ast.While):
                while eval_node(node.test, local_vars):
                    step_nodes(node.body, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            elif isinstance(node, ast.If):
                branch = node.body if eval_node(node.test, local_vars) else node.orelse
                step_nodes(branch, local_vars)

            elif isinstance(node, ast.With):
                exits = []
                for item in node.items:
                    context = eval_node(item.context_expr, local_vars)
                    value = context.__enter__()
                    if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                        (local_vars or exec_globals)[item.optional_vars.id] = value
                    exits.append(context.__exit__)
                try:
                    step_nodes(node.body, local_vars)
                finally:
                    for exit_ in reversed(exits):
                        exit_(None, None, None)

            elif isinstance(node, ast.Try):
                try:
                    step_nodes(node.body, local_vars)
                except Exception as error:
                    handled = False
                    for handler in node.handlers:
                        if handler.type is None or isinstance(error, eval_node(handler.type, local_vars)):
                            step_nodes(handler.body, local_vars)
                            handled = True
                            break
                    if not handled:
                        raise
                finally:
                    step_nodes(node.finalbody, local_vars)
                if node.orelse:
                    step_nodes(node.orelse, local_vars)

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_name = alias.name
                        asname = alias.asname or alias.name
                        mod_path = Path(mod_name.replace('.', '/') + '.py')
                        if mod_path.exists():
                            mod_obj = types.ModuleType(mod_name)
                            imported_globals = stepper(mod_path, module_name=mod_name)
                            mod_obj.__dict__.update(imported_globals)
                            (local_vars or exec_globals)[asname] = mod_obj
                        else:
                            (local_vars or exec_globals)[asname] = __import__(mod_name)
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module
                    mod_path = Path(mod_name.replace('.', '/') + '.py')
                    if mod_path.exists():
                        mod_obj = types.ModuleType(mod_name)
                        imported_globals = stepper(mod_path, module_name=mod_name)
                        mod_obj.__dict__.update(imported_globals)
                        for alias in node.names:
                            name = alias.name
                            asname = alias.asname or name
                            (local_vars or exec_globals)[asname] = mod_obj.__dict__[name]
                    else:
                        mod = __import__(mod_name, fromlist=[alias.name for alias in node.names])
                        for alias in node.names:
                            name = alias.name
                            asname = alias.asname or name
                            (local_vars or exec_globals)[asname] = getattr(mod, name)

            else:
                print(f"\033[1;31mUnknown node: {type(node).__name__}\033[1;37m")
                exec_node(node, local_vars)

    source = file_path.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=file_path.name)
    step_nodes(parsed.body, exec_globals)
    return exec_globals

if __name__ == '__main__':
    from settrace import pretty_json, filter_scope, use_dir, argv
    script_path = Path(argv[1]).resolve()
    assert script_path.name == 'test.py', 'this script is in dev!'
    with use_dir(script_path.parent):
        stepper(script_path)
