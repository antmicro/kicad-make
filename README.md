# kmake

Copyright (c) 2019-2024 [Antmicro](https://www.antmicro.com)

`kmake` is a simple utility that automates handling of [KiCad](https://www.kicad.org/) projects.
`kmake` provides a unified way to generate KiCad production files and manage project structure.
The script can be used locally and in conjunction with CI infrastructure.
`Kmake` is developed with KiCad 7+ and a CI environment in mind.
It uses the KiCad CLI where possible and [kiutils](https://github.com/mvnmgrx/kiutils) for functions that require raw file manipulation.

## Documentation

Visit the [`kmake` documentation](https://antmicro.github.io/kmake/) for more information about usage and development of `kmake`.

## Installation

### Requirements

`kmake` depends on the following packages:

* `KiCad 7.0.x`
* `python >= 3.7`
* `pip`

### Installation (Debian)

1. Configure PATH:

    ```bash
    export PATH=$HOME/.local/bin:$PATH
    ```

2. Install requirements

    ```bash
    sudo apt install kicad python3 python3-pip
    ```

    > Note: Kmake requires also Python `pcbnew` module normally added to the Python modules path during [KiCad](https://www.kicad.org/) native installation.

3. Clone `kmake` repository:

    ```bash
    git clone https://github.com/antmicro/kmake
    cd kmake
    python3 -m pip install .
    ```

    > Important: In some system configurations you may need to add the `--break-system-packages` flag to the command above.

## Usage

> Important: All commands should be issued from the KiCad project root directory.

To show available functionalities run:

```bash
cd <KiCad project directory>
kmake --help
```

## Version

As an convention, the `kmake` version is derived from the `KiCad` version supported by the release.
For example, `kmake` version `7.0.x` supports `KiCad` version `7.0.x`.

To check which version of `kmake` is installed in your system, run:

```bash
python3 -m pip show kmake | grep "Version:"
```

## License

This project is licensed under the [Apache-2.0](LICENSE) license.
