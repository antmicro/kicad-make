# Development

## Repo structure

`kmake` repo structure:

```text
.
├── docs
│   ├── ...
│   └── source
│       ├── img
│       │   └── ...
│       ├── ...
│       ├── installation.md
│       └── index.md
├── LICENSE
├── README.md
├── pyproject.toml
└── src
    ├── commands
    │   ├── __init__.py
    │   ├── auxorigin.py
    │   ├── ...
    │   └── wireframe.py
    ├── common
    │   ├── kicad_project.py
    │   └── kmake_helper.py
    ├── ext_modules
    │   └── example.py
    └── kmake.py
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
- `warning`
- `error`

## New command example

Sample `__init__.py` and `new_command.py` file contents:

```{tab} commands/__init__.py
add following line to `__init__.py`

    from . import new_command

```

```{tab} commands/new_command.py
    """Minimal working command"""
    import logging

    from common.kicad_project import KicadProject

    log = logging.getLogger(__name__)


    def add_subparser(subparsers):
        """Register parser and its arguments as subparser"""
        new_function_parser = subparsers.add_parser(
            "example", help=""
        )
        # Example argument
        new_function_parser.add_argument(
            "-p",
            "--print",
            dest="print",
            action="store_true",
            help="Prints hello message",
        )
        new_function_parser.set_defaults(func=run)


    def main(project:KicadProject, args):
        """Main module function"""
        if args.print:
            log.info(f"Hello from example, running in {project.dir}")

    def run(project:KicadProject, args):
        """Entry function for module"""
        main(project, args)


```

## Generating tests coverage report

To generate a coverage report of the tests, execute:

```bash
poetry run pytest --cov-report term --cov-report html:htmlcov --cov=src
```

The result will be printed in the terminal and saved as an HTML report to `htmlcov`.
