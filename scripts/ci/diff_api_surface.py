"""Compute a diff of the public Python API between two trees."""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

API_ROOT = Path("src")


@dataclass(frozen=True)
class ModuleContents:
    """Representation of the public API for a single module."""

    functions: Mapping[str, str]
    classes: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class SignatureChange:
    """Describe a signature change for a function or method."""

    previous: str
    current: str


@dataclass
class ApiDiff:
    """Collection of API changes between two snapshots."""

    added_functions: Dict[str, str]
    removed_functions: Dict[str, str]
    changed_functions: Dict[str, SignatureChange]
    added_classes: Dict[str, Mapping[str, str]]
    removed_classes: Dict[str, Mapping[str, str]]
    added_methods: Dict[str, str]
    removed_methods: Dict[str, str]
    changed_methods: Dict[str, SignatureChange]

    def is_empty(self) -> bool:
        return not (
            self.added_functions
            or self.removed_functions
            or self.changed_functions
            or self.added_classes
            or self.removed_classes
            or self.added_methods
            or self.removed_methods
            or self.changed_methods
        )


def module_name_from_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative.suffix != ".py":
        raise ValueError(f"Expected Python file, got {relative}")
    parts = list(relative.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def format_annotation(annotation: ast.expr | None) -> str:
    if annotation is None:
        return ""
    return f": {ast.unparse(annotation)}"


def format_default(default: ast.expr | None) -> str:
    if default is None:
        return ""
    return f" = {ast.unparse(default)}"


def format_arg(arg: ast.arg, default: ast.expr | None) -> str:
    return f"{arg.arg}{format_annotation(arg.annotation)}{format_default(default)}"


def format_arguments(args: ast.arguments) -> str:
    parts: List[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = list(args.defaults)
    default_offset = len(positional) - len(defaults)

    for index, arg in enumerate(args.posonlyargs):
        default = defaults[index - default_offset] if index >= default_offset else None
        parts.append(format_arg(arg, default))
    if args.posonlyargs:
        parts.append("/")

    for index, arg in enumerate(args.args):
        absolute_index = len(args.posonlyargs) + index
        default = (
            defaults[absolute_index - default_offset]
            if absolute_index >= default_offset
            else None
        )
        parts.append(format_arg(arg, default))

    if args.vararg is not None:
        vararg = f"*{args.vararg.arg}{format_annotation(args.vararg.annotation)}"
        parts.append(vararg)

    if args.kwonlyargs:
        if args.vararg is None:
            parts.append("*")
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            parts.append(format_arg(arg, default))

    if args.kwarg is not None:
        parts.append(f"**{args.kwarg.arg}{format_annotation(args.kwarg.annotation)}")

    return f"({', '.join(parts)})"


def format_signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        signature = f"{async_prefix}{format_arguments(node.args)}"
        if node.returns is not None:
            signature = f"{signature} -> {ast.unparse(node.returns)}"
        return signature
    raise TypeError(f"Unsupported node: {type(node)!r}")


def extract_module_api(source: str) -> ModuleContents:
    tree = ast.parse(source)
    functions: Dict[str, str] = {}
    classes: Dict[str, Dict[str, str]] = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            functions[node.name] = format_signature(node)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            methods: Dict[str, str] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_"):
                        continue
                    methods[item.name] = format_signature(item)
            classes[node.name] = methods

    return ModuleContents(functions=functions, classes=classes)


def snapshot_from_directory(root: Path) -> Mapping[str, ModuleContents]:
    modules: Dict[str, ModuleContents] = {}
    if not root.exists():
        return modules
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        module_name = module_name_from_path(path, root)
        if not module_name:
            continue
        modules[module_name] = extract_module_api(path.read_text(encoding="utf-8"))
    return modules


def snapshot_from_git(ref: str, repo_root: Path, tree: Path = API_ROOT) -> Mapping[str, ModuleContents]:
    modules: Dict[str, ModuleContents] = {}
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, str(tree)],
            cwd=repo_root,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return modules

    for line in result.stdout.splitlines():
        if not line.endswith(".py"):
            continue
        file_path = Path(line)
        module_name = module_name_from_path(file_path, tree)
        if not module_name:
            continue
        try:
            show = subprocess.run(
                ["git", "show", f"{ref}:{line}"],
                cwd=repo_root,
                capture_output=True,
                check=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            continue
        modules[module_name] = extract_module_api(show.stdout)
    return modules


def compute_api_diff(
    base_snapshot: Mapping[str, ModuleContents],
    head_snapshot: Mapping[str, ModuleContents],
) -> ApiDiff:
    diff = ApiDiff(
        added_functions={},
        removed_functions={},
        changed_functions={},
        added_classes={},
        removed_classes={},
        added_methods={},
        removed_methods={},
        changed_methods={},
    )

    module_names = set(base_snapshot) | set(head_snapshot)
    for module in sorted(module_names):
        base_module = base_snapshot.get(module)
        head_module = head_snapshot.get(module)
        if base_module is None and head_module is not None:
            for name, signature in head_module.functions.items():
                diff.added_functions[f"{module}.{name}"] = signature
            for name, methods in head_module.classes.items():
                diff.added_classes[f"{module}.{name}"] = methods
            continue
        if head_module is None and base_module is not None:
            for name, signature in base_module.functions.items():
                diff.removed_functions[f"{module}.{name}"] = signature
            for name, methods in base_module.classes.items():
                diff.removed_classes[f"{module}.{name}"] = methods
            continue
        if base_module is None or head_module is None:
            continue

        function_names = set(base_module.functions) | set(head_module.functions)
        for name in sorted(function_names):
            qualified = f"{module}.{name}"
            base_sig = base_module.functions.get(name)
            head_sig = head_module.functions.get(name)
            if base_sig is None and head_sig is not None:
                diff.added_functions[qualified] = head_sig
            elif head_sig is None and base_sig is not None:
                diff.removed_functions[qualified] = base_sig
            elif base_sig != head_sig and base_sig is not None and head_sig is not None:
                diff.changed_functions[qualified] = SignatureChange(base_sig, head_sig)

        class_names = set(base_module.classes) | set(head_module.classes)
        for name in sorted(class_names):
            qualified_class = f"{module}.{name}"
            base_methods = base_module.classes.get(name)
            head_methods = head_module.classes.get(name)
            if base_methods is None and head_methods is not None:
                diff.added_classes[qualified_class] = head_methods
                continue
            if head_methods is None and base_methods is not None:
                diff.removed_classes[qualified_class] = base_methods
                continue
            if base_methods is None or head_methods is None:
                continue

            method_names = set(base_methods) | set(head_methods)
            for method_name in sorted(method_names):
                qualified_method = f"{qualified_class}.{method_name}"
                base_method = base_methods.get(method_name)
                head_method = head_methods.get(method_name)
                if base_method is None and head_method is not None:
                    diff.added_methods[qualified_method] = head_method
                elif head_method is None and base_method is not None:
                    diff.removed_methods[qualified_method] = base_method
                elif (
                    base_method is not None
                    and head_method is not None
                    and base_method != head_method
                ):
                    diff.changed_methods[qualified_method] = SignatureChange(
                        base_method, head_method
                    )

    return diff


def render_markdown(diff: ApiDiff) -> str:
    if diff.is_empty():
        return "No public API changes detected."

    lines: List[str] = []
    if diff.added_functions:
        lines.append("#### Added functions")
        for name in sorted(diff.added_functions):
            signature = diff.added_functions[name]
            lines.append(f"- `{name}`: {signature}")
        lines.append("")

    if diff.removed_functions:
        lines.append("#### Removed functions")
        for name in sorted(diff.removed_functions):
            signature = diff.removed_functions[name]
            lines.append(f"- `{name}`: {signature}")
        lines.append("")

    if diff.changed_functions:
        lines.append("#### Modified functions")
        for name in sorted(diff.changed_functions):
            change = diff.changed_functions[name]
            lines.append(
                f"- `{name}`: {change.previous} → {change.current}"
            )
        lines.append("")

    if diff.added_classes:
        lines.append("#### Added classes")
        for name in sorted(diff.added_classes):
            methods = diff.added_classes[name]
            method_list = ", ".join(sorted(methods)) if methods else "no public methods"
            lines.append(f"- `{name}` (methods: {method_list})")
        lines.append("")

    if diff.removed_classes:
        lines.append("#### Removed classes")
        for name in sorted(diff.removed_classes):
            methods = diff.removed_classes[name]
            method_list = ", ".join(sorted(methods)) if methods else "no public methods"
            lines.append(f"- `{name}` (methods: {method_list})")
        lines.append("")

    if diff.added_methods:
        lines.append("#### Added methods")
        for name in sorted(diff.added_methods):
            signature = diff.added_methods[name]
            lines.append(f"- `{name}`: {signature}")
        lines.append("")

    if diff.removed_methods:
        lines.append("#### Removed methods")
        for name in sorted(diff.removed_methods):
            signature = diff.removed_methods[name]
            lines.append(f"- `{name}`: {signature}")
        lines.append("")

    if diff.changed_methods:
        lines.append("#### Modified methods")
        for name in sorted(diff.changed_methods):
            change = diff.changed_methods[name]
            lines.append(
                f"- `{name}`: {change.previous} → {change.current}"
            )
        lines.append("")

    return "\n".join(lines).strip()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base directory or git ref")
    parser.add_argument("--head", required=True, help="Head directory or git ref")
    parser.add_argument(
        "--mode",
        choices=["path", "git"],
        default="path",
        help="Interpret arguments as filesystem paths or git refs.",
    )
    parser.add_argument(
        "--repo",
        default=str(Path.cwd()),
        help="Repository root when --mode=git is used.",
    )
    parser.add_argument(
        "--root",
        default=str(API_ROOT),
        help="Subdirectory containing the Python package (defaults to src).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_snapshot(args: argparse.Namespace, ref: str) -> Mapping[str, ModuleContents]:
    root = Path(args.root)
    if args.mode == "git":
        return snapshot_from_git(ref, Path(args.repo), root)
    return snapshot_from_directory(Path(ref))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    base_snapshot = load_snapshot(args, args.base)
    head_snapshot = load_snapshot(args, args.head)
    diff = compute_api_diff(base_snapshot, head_snapshot)
    print(render_markdown(diff))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
