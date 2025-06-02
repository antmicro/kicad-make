# KiCad Make (kmake)

Copyright (c) 2019-2025 [Antmicro](https://www.antmicro.com)

This is a simple utility that automates handling of [KiCad](https://www.kicad.org/) projects.
`kmake` provides a unified way to generate KiCad production files and manage project structure.
The script can be used locally and in conjunction with CI infrastructure.
`Kmake` is developed with KiCad 8+ and a CI environment in mind.
It uses the KiCad CLI where possible and [kiutils](https://github.com/antmicro/kiutils) for functions that require raw file manipulation.

> KiCad 8 files should be fully supported (they will be upgraded on fly), however this has not been extensively tested.

## Documentation

Visit the [`kmake` documentation](https://antmicro.github.io/kicad-make/) for more information about usage and development of `kmake`.

## Installation

### Requirements

`kmake` depends on the following packages:

* `KiCad 9.0.x`
* `python >= 3.7`

### Installation (Debian)

1. Install requirements

    ```bash
    sudo apt install kicad python3 pipx
    pipx ensurepath
    ```

2. Clone and install `kmake` repository:

    ```bash
    pipx install 'git+https://github.com/antmicro/kicad-make.git'
    ```

## Usage

> Important: All commands should be issued from the KiCad project root directory.

To show available functionalities run:

```bash
cd <KiCad project directory>
kmake --help
```

## Version

As an convention, the `kmake` version is derived from the `KiCad` version supported by the release.
For example, `kmake` version `9.0.x` supports `KiCad` version `9.0.x`.

To check which version of `kmake` is installed in your system, run:

```bash
kmake version
```

## Licensing

This project is licensed under the [Apache-2.0](LICENSE) license.
