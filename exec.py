import ast
import types
from pathlib import Path

def stepper(file_path: Path, exec_globals=None, module_name=None):
    module_name = module_name or '__main__'
    exec_globals = exec_globals or {'__file__': str(file_path), '__name__': module_name}

    class ReturnValue(BaseException):
        def __init__(self, value):
            self.value = value

    class BreakSignal(BaseException): pass
    class ContinueSignal(BaseException): pass

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

    def make_ast_from_value(value):
        return ast.parse(repr(value), mode='eval').body

    def exec_node(node, local_vars=None):
        exec(compile_node(node, 'exec'), exec_globals, local_vars)

    def eval_node(node, local_vars=None):
        if isinstance(node, ast.Name):
            if local_vars and node.id in local_vars:
                return local_vars[node.id]
            return exec_globals.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value

        temp_globals = exec_globals.copy()
        if local_vars:
            temp_globals.update(local_vars)

        return eval(compile_node(node, 'eval'), temp_globals, {})

    def pattern_matches(pattern, value, local_vars):
        match pattern:
            case ast.MatchAs(name=None, pattern=None):
                return True
            case ast.MatchAs(name, None):
                (local_vars or exec_globals)[name] = value
                return True
            case ast.MatchValue(value=const):
                return eval_node(const, local_vars) == value
            case ast.MatchSingleton(value=const):
                return const is value
            case ast.MatchSequence(patterns=patterns):
                if not isinstance(value, (list, tuple)) or len(value) != len(patterns):
                    return False
                return all(pattern_matches(p, v, local_vars) for p, v in zip(patterns, value))
            case ast.MatchMapping(keys=keys, patterns=patterns):
                if not isinstance(value, dict):
                    return False
                for key, pat in zip(keys, patterns):
                    key_val = eval_node(key, local_vars)
                    if key_val not in value or not pattern_matches(pat, value[key_val], local_vars):
                        return False
                return True
            case ast.MatchClass(cls, patterns, kwd_attrs, kwd_patterns):
                cls_eval = eval_node(cls, local_vars)
                if not isinstance(value, cls_eval):
                    return False
                args = getattr(value, "__match_args__", ())
                for pat, attr in zip(patterns, args):
                    if not pattern_matches(pat, getattr(value, attr), local_vars):
                        return False
                for attr, pat in zip(kwd_attrs, kwd_patterns):
                    if not pattern_matches(pat, getattr(value, attr), local_vars):
                        return False
                return True
            case ast.MatchOr(patterns=patterns):
                return any(pattern_matches(p, value, local_vars) for p in patterns)
            case _:
                print(f"\033[1;31mUnknown match pattern: {type(pattern).__name__}\033[1;37m")
                return False

    def step_nodes(nodes, local_vars=None):
        for node in nodes:
            if 'scope' in argv: 
                print(f'\033[32m{pretty_json(filter_scope(local_vars))}\033[1;37m')
            (print if 'skip' in argv else input)(f"\033[1;31m>>> \033[33m{ast.unparse(node)}\033[1;37m")

            match node:
                case ast.FunctionDef():
                    def make_func(node):
                        arg_names = [arg.arg for arg in node.args.args]
                        defaults = [eval_node(d, local_vars) for d in node.args.defaults] if node.args.defaults else []
                        default_map = dict(zip(arg_names[-len(defaults):], defaults)) if defaults else {}

                        def func(*args, **kwargs):
                            local_vars_inner = dict(zip(arg_names, args))
                            for name in arg_names[len(args):]:
                                if name in kwargs:
                                    local_vars_inner[name] = kwargs.pop(name)
                                elif name in default_map:
                                    local_vars_inner[name] = default_map[name]
                                else:
                                    raise TypeError(f"{node.name}() missing required argument: '{name}'")
                            local_vars_inner.update(kwargs)
                            try:
                                step_nodes(node.body, local_vars_inner)
                            except ReturnValue as rv:
                                return rv.value
                        return func

                    (local_vars or exec_globals)[node.name] = make_func(node)

                case ast.ClassDef():
                    exec_node(node, local_vars)

                case ast.Return():
                    if local_vars is None:
                        raise SyntaxError("'return' outside function")
                    value = eval_node(node.value, local_vars) if node.value else None
                    raise ReturnValue(value)

                case ast.Expr():
                    eval_node(node.value, local_vars)

                case ast.Assign():
                    value = eval_node(node.value, local_vars)
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            (local_vars or exec_globals)[target.id] = value
                        elif isinstance(target, ast.Tuple):
                            for t, v in zip(target.elts, value):
                                (local_vars or exec_globals)[t.id] = v
                        else:
                            exec_node(located(ast.Assign(targets=[target], value=make_ast_from_value(value)), node), local_vars)

                case ast.For():
                    for item in eval_node(node.iter, local_vars):
                        if isinstance(node.target, ast.Name):
                            (local_vars or exec_globals)[node.target.id] = item
                        else:
                            exec_node(located(ast.Assign(targets=[node.target], value=make_ast_from_value(item)), node), local_vars)
                        try:
                            step_nodes(node.body, local_vars)
                        except ContinueSignal:
                            continue
                        except BreakSignal:
                            break
                    else:
                        if node.orelse:
                            step_nodes(node.orelse, local_vars)

                case ast.While():
                    while eval_node(node.test, local_vars):
                        try:
                            step_nodes(node.body, local_vars)
                        except ContinueSignal:
                            continue
                        except BreakSignal:
                            break
                    else:
                        if node.orelse:
                            step_nodes(node.orelse, local_vars)

                case ast.Break():
                    raise BreakSignal()

                case ast.Continue():
                    raise ContinueSignal()

                case ast.If():
                    branch = node.body if eval_node(node.test, local_vars) else node.orelse
                    step_nodes(branch, local_vars)

                case ast.With():
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

                case ast.Try():
                    no_exc = True
                    try:
                        step_nodes(node.body, local_vars)
                    except ReturnValue:
                        no_exc = False
                        raise
                    except Exception as error:
                        no_exc = False
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
                    if no_exc and node.orelse:
                        step_nodes(node.orelse, local_vars)

                case ast.Import():
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

                case ast.ImportFrom():
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

                case ast.Match():
                    subject_value = eval_node(node.subject, local_vars)
                    matched = False
                    for case_ in node.cases:
                        if pattern_matches(case_.pattern, subject_value, local_vars):
                            if case_.guard is None or eval_node(case_.guard, local_vars):
                                step_nodes(case_.body, local_vars)
                                matched = True
                                break
                    if not matched:
                        pass
                
                case ast.Delete() | ast.AugAssign():
                    exec_node(node, local_vars)

                case _:
                    print(f"\033[1;31mUnknown node: {type(node).__name__}\033[1;37m")
                    exec_node(node, local_vars)

    source_code = file_path.read_text(encoding="utf-8")
    parsed_ast = ast.parse(source_code, filename=file_path.name)
    step_nodes(parsed_ast.body, exec_globals)
    return exec_globals

if __name__ == '__main__':
    from settrace import pretty_json, filter_scope, use_dir, argv
    script_path = Path(argv[1]).resolve()
    assert script_path.name == 'test.py', 'this script is in dev!'
    with use_dir(script_path.parent):
        stepper(script_path)
