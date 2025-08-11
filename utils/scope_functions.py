#!/usr/bin/env python3

startswith = str.startswith

def filter_scope(scope: dict):
    return {key: value for key, value in scope.items() if not startswith(key, "__")}

def diff_scope(old_scope: dict, new_scope: dict):
    if old_scope is new_scope:
        return {}
    changes = {key: value for key, value in new_scope.items() if old_scope.get(key) != value}
    deleted = {key: "<deleted>" for key in old_scope.keys() - new_scope.keys()}
    return {**changes, **deleted}
