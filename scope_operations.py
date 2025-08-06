#!/usr/bin/env python3

from copy import deepcopy

scope_history = {}  # {(filename, funcname): [(lineno, diff_dict)]}
last_scopes = {}    # {(filename, funcname): latest_full_scope}

def filter_scope(scope):
    return {key: value for key, value in scope.items() if not key.startswith("__")}

def diff_scope(old, new):
    diff = {}
    for key in new:
        if key not in old or old[key] != new[key]:
            diff[key] = new[key]
    for key in old:
        if key not in new:
            diff[key] = None  # Mark as deleted
    return diff

def apply_diff(scope, diff):
    scope = deepcopy(scope)
    for k, v in diff.items():
        if v is None:
            scope.pop(k, None)
        else:
            scope[k] = v
    return scope

def get_full_scope(filename, funcname=None, upto_lineno=None):
    key = (filename, funcname)
    full_scope = {}
    for lineno, diff in scope_history.get(key, []):
        if upto_lineno is not None and lineno > upto_lineno:
            break
        full_scope = apply_diff(full_scope, diff)
    return full_scope
