"""File and working directory helper scripts"""

from pathlib import Path

import logging
import os
import subprocess

log = logging.getLogger(__name__)


def is_in_path(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def get_kicad_cli_command() -> tuple[str, list[str]]:
    try:
        kicad_cli_name = os.environ["KMAKE_KICAD_CLI"]
        kicad_cli_path = kicad_cli_name.split(" ")[0]
        kicad_cli_args = kicad_cli_name.split(" ")[1:]
    except KeyError:
        kicad_cli_path = "kicad-cli"
        kicad_cli_args = []
    if not is_in_path(kicad_cli_path):
        raise FileNotFoundError(
            f'Couldn\'t find "{kicad_cli_path}" in PATH. Make sure it is properly installed on your system. Exiting.'
        )
    return kicad_cli_path, kicad_cli_args


def run_kicad_cli(args: list[str | Path], verbose: bool) -> None:
    kicad_cli_path, kicad_cli_args = get_kicad_cli_command()
    command = [kicad_cli_path] + kicad_cli_args
    command.extend(str(a) for a in args)
    log.info(f"Running command: {' '.join(command)}")
    stdout_redirect = None
    stderr_redirect = None
    if not verbose:
        stdout_redirect = subprocess.DEVNULL
        stderr_redirect = subprocess.STDOUT

    subprocess.run(command, check=True, stdout=stdout_redirect, stderr=stderr_redirect)
