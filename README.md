# foundry

Utilities for turning a plain project idea into a runnable Python package. The
package ships with a small command line interface as well as programmatic APIs
for:

- Generating predictable identifiers (slug, package name, class name) from a
  human friendly project title.
- Rendering moustache-style templates without pulling in heavyweight
  dependencies.
- Scaffolding a minimal Python project ready for iteration.

## Installation

The project uses the `src/` layout. Install it in editable mode to experiment
with the tooling:

```bash
pip install -e .[dev]
```

## Command line usage

```
$ python -m foundry.cli init "My Project" --directory ./my-project
Project created at /abs/path/to/my-project
```

The `render` sub-command renders individual template files:

```
$ python -m foundry.cli render template.txt -c name=demo -o output.txt
```

## Programmatic usage

```python
from foundry import ProjectConfig, ProjectScaffolder, TemplateRenderer

config = ProjectConfig.from_name("Example App", description="Demo project")
scaffolder = ProjectScaffolder()
project_path = scaffolder.create(config, "./example-app")

renderer = TemplateRenderer()
renderer.render_string("Hello {{ name|upper }}", {"name": "world"})
```
