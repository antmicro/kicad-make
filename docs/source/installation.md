# Installation

## Requirements

Kmake is designed to work with `KiCad 7.x`.
Kmake requires: `python3` and `python3-pip` installed.

## Installation (Debian)

1. Configure PATH:

    ```bash
    export PATH=$HOME/.local/bin:$PATH
    ```

1. Install requrements

    ```bash
    sudo apt install kicad python3 python3-pip
    ```

    Kmake requires also python `pcbnew` module, which is normally added to python
    modules path during [KiCad](https://www.kicad.org/) native installation.

1. Update `pip`

    ```bash
    python3 -m pip install --upgrade pip
    ```

1. Clone and install `kmake`:

    ```bash
    git clone https://github.com/antmicro/kmake
    cd kmake
    python3 -m pip install .
    ```

    > Important: In some system configurations you may need to add
    `--break-system-packages` flag to above command.

## Basic usage

> Important: All commands should be issued from KiCad project root directory.

To show available functionalities run:

```bash
cd <KiCad project directory>
kmake --help
```
