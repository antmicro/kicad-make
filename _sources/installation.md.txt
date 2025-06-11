# Installation

## Requirements

Kmake is designed to work with `KiCad 9.x`.
Kmake requires: `python3` installed.

## Installation (Debian)

1. Install requirements

    ```bash
    sudo apt install kicad python3 pipx
    pipx ensurepath
    ```

2. Clone and install `kmake` repository:

    ```bash
    pipx install 'git+https://github.com/antmicro/kicad-make.git'
    ```


## Basic usage

> Important: All commands should be issued from KiCad project root directory.

To show available functionalities run:

```bash
cd <KiCad project directory>
kmake --help
```
