"""Command line interface for the foundry utilities."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence

from .config import ProjectConfig
from .scaffold import ProjectScaffolder
from .template import TemplateRenderer


def _parse_key_value_pairs(pairs: Iterable[str]) -> dict[str, str]:
    context: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise argparse.ArgumentTypeError(
                f"invalid key/value pair '{pair}'. Expected KEY=VALUE syntax."
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise argparse.ArgumentTypeError("keys must not be empty")
        context[key] = value
    return context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Utilities for scaffolding projects")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a new project scaffold")
    init_parser.add_argument("name", help="Display name for the new project")
    init_parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="Target directory where the project should be created",
    )
    init_parser.add_argument("--package", help="Override the generated package name")
    init_parser.add_argument("--class-name", help="Override the generated class name")
    init_parser.add_argument("--description", default="", help="Project description")
    init_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files instead of failing",
    )

    render_parser = subparsers.add_parser(
        "render", help="render a template file with simple moustache style placeholders"
    )
    render_parser.add_argument("template", type=Path, help="Path to the template file")
    render_parser.add_argument(
        "-c",
        "--context",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        help="Values exposed to the template renderer",
    )
    render_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write the rendered template to this path instead of stdout",
    )
    render_parser.add_argument(
        "--missing",
        choices=["keep", "empty", "error"],
        default="keep",
        help="Behaviour when a placeholder cannot be resolved",
    )

    return parser


def _handle_init(args: argparse.Namespace) -> int:
    config = ProjectConfig.from_name(
        args.name,
        package=args.package,
        class_name=args.class_name,
        description=args.description,
    )
    renderer = TemplateRenderer()
    scaffolder = ProjectScaffolder(renderer)
    target = args.directory
    target.mkdir(parents=True, exist_ok=True)
    project_path = scaffolder.create(config, target, force=args.force)
    print(f"Project created at {project_path}")
    return 0


def _handle_render(args: argparse.Namespace) -> int:
    renderer = TemplateRenderer()
    context = _parse_key_value_pairs(args.context)
    rendered = renderer.render_file(args.template, context, missing=args.missing)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return _handle_init(args)
    if args.command == "render":
        return _handle_render(args)
    parser.error("no command provided")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
