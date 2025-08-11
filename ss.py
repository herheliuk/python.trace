import timeit

def default_json_handler_1(obj):
    filename = type(obj).__name__
    return f"<{filename}>"

def default_json_handler_2(obj): 
    return f"<{type(obj).__name__}>"

test_obj = 123

time_1 = timeit.timeit('default_json_handler_1(test_obj)', globals=globals(), number=1_000_000)
time_2 = timeit.timeit('default_json_handler_2(test_obj)', globals=globals(), number=1_000_000)

print(f"Multi-line function time: {time_1:.6f}")
print(f"One-liner function time: {time_2:.6f}")
