# Development

## Repo structure

`kmake` repo structure:

```bash
.
├── Dockerfile
├── docs
│   ├── Makefile
│   ├── requirements.txt
│   └── source
│       ├── conf.py
│       ├── ...
│       └── usage.md
├── LICENSE
├── pyproject.toml
├── README.md
├── src
│   ├── commands
│   │   ├── auxorigin.py
│   │   ├── ...
│   │   └── wireframe.py
│   ├── common
│   │   ├── __init__.py
│   │   ├── kicad_project.py
│   │   └── kmake_helper.py
│   ├── __init__.py
│   ├── kmake.py
│   └── logos
│       └── oshw
└── tests
    ├── designs
    │   └── designs.list
    ├── test_auxorigin.py
    ├── ...
    └── test_wireframe.py
```

## Commands

Commands are stored in the `commands` directory.

You can add a custom command by creating a file inside the `commands` directory and
importing it in `__init__.py`.

The following rules apply:

- `add_subparser(subparsers)` and `run(project, args)` functions need to be defined
- Command line arguments are passed as `args` object to the `run(project, args)`
    function
- The `KicadProject` class object is passed to `run(project, args)`.

## Printing and logging

All printing is handled using `log` inherited from `kmake`.
There are 4 levels of logging:

- `info` - for state updates, for example: "Opening PCB for read" or
    "Saving PCB to file path_to_the_file"
- `debug` - for information relevant to debugging, for example:
    "Processing footprint abc from library xyz".
- `warning` - for non critical fails, for example: "Symbol xyz has no mpn to match, it will be omitted"
- `error` - for critical fails: "KiCad project not found"

## New command example

Sample `__init__.py` and `new_command.py` file contents:

```{tab} commands/__init__.py
add following line to `__init__.py`
```python
from . import new_command
```

```{tab} commands/new_command.py
```python
# Minimal working command
import logging
import argparse
from common.kicad_project import KicadProject

log = logging.getLogger(__name__)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    # Register parser and its arguments as subparser
    new_function_parser = subparsers.add_parser("example", help="")
    # Example argument
    new_function_parser.add_argument(
        "-p",
        "--print",
        dest="print",
        action="store_true",
        help="Prints hello message",
    )
    new_function_parser.set_defaults(func=run)


def main(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    # Main module function
    if args.print:
        log.info(f"Hello from example, running in {kicad_project.dir}")


def run(kicad_project: KicadProject, args: argparse.Namespace) -> None:
    # Entry function for module
    main(kicad_project, args)

```

## Generating tests coverage report

To generate a coverage report of the tests, execute:

```bash
poetry run pytest --cov-report term --cov-report html:htmlcov --cov=src
```

The result will be printed in the terminal and saved as an HTML report to `htmlcov`.
