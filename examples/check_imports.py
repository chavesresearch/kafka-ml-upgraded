#!/usr/bin/env python3
"""Import-resolution smoke test for one examples/* tutorial script directory.

Doesn't execute the scripts themselves - they open a live KafkaProducer/
KafkaConsumer at import time with no CI Kafka broker available, and several
also download a real dataset. This only proves every module the scripts
actually import (parsed from their real `import`/`from` statements, not a
hand-maintained parallel list) resolves against the directory's
requirements.txt - the class of failure that bit-rot (a stale pin that no
longer installs, or whose API moved) causes.

Usage: python check_imports.py <example-directory>
"""
import ast
import importlib
import pathlib
import sys

target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
failures = []
checked = 0

for py_file in sorted(target.glob("*.py")):
    checked += 1
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue  # relative import, not a third-party dependency
            modules = [node.module] if node.module else []
        else:
            continue
        for module in modules:
            root = module.split(".")[0]
            try:
                importlib.import_module(root)
            except ImportError as exc:
                failures.append(f"{py_file.name}: `import {module}` failed: {exc}")

if not checked:
    print(f"No .py files found under {target}")
    sys.exit(1)

if failures:
    print(f"Import check FAILED ({len(failures)} failure(s)):")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)

print(f"OK: every import across {checked} script(s) in {target} resolved.")
