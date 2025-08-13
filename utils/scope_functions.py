#!/usr/bin/env python3

def filter_scope(scope: dict):
    return {key: value for key, value in scope.items() if key[:2] != "__"}

def diff_scope(old_scope: dict, new_scope: dict):
    return {
        key: new_scope[key] if key in new_scope else "<deleted>"
        for key in old_scope.keys() | new_scope.keys()
        if old_scope.get(key) != new_scope.get(key)
    }

