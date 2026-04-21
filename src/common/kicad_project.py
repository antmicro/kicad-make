"""KiCad project class"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from askiff import Project
from askiff.common import LibraryTable

from .kmake_helper import get_kicad_cli_command

log = logging.getLogger(__name__)


class KicadProject(Project):
    sch_ext: str = "kicad_sch"
    pro_ext: str = "kicad_pro"
    pcb_ext: str = "kicad_pcb"
    dru_ext: str = "kicad_dru"
    sym_lib_ext: str = "kicad_sym"
    fp_lib_ext: str = "kicad_mod"
    relative_fab_path: str = "fab"
    relative_doc_path: str = "doc"
    relative_step_model3d_path: str = "3d-model"
    relative_lib_path: str = "lib"
    relative_fp_lib_path: str = "footprints"
    relative_3d_model_path: str = "3d-models"
    local_share_path: Path = Path(os.path.expandvars("$HOME/.local/share"))

    system_fp_lib_table = "/usr/share/kicad/template/fp-lib-table"
    system_sym_lib_table = "/usr/share/kicad/template/sym-lib-table"

    fab_dir: Path
    doc_dir: Path
    step_model3d_dir: Path
    lib_dir: Path
    fp_lib_dir: Path
    model_3d_lib_dir: Path

    def __init__(self, path: Path, disable_logging: bool = False, local_share_path: Path | None = None) -> None:
        """Manage kicad files

        Parameters:
                disable_logging (bool): do not log when no KiCad file exists
        """
        Project.__init__(self, path=path)
        self.load()
        self.disable_logging = disable_logging
        if local_share_path is not None:
            self.local_share_path = Path(local_share_path)

        self.pcb_file: str = ""

        # Get KiCad version
        kicad_cli_name = get_kicad_cli_command()[0]
        self.kicad_version_full = subprocess.run(
            [kicad_cli_name, "--version"], text=True, check=True, capture_output=True
        ).stdout.strip()
        self.kicad_version = ".".join(self.kicad_version_full.split(".")[0:2])

        self.comm_cfg_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/kicad_common.json")
        self.glob_fp_lib_table_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/fp-lib-table")
        self.glob_sym_lib_table_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/sym-lib-table")

        self.env_var_name_sym_lib = f"KICAD{self.kicad_version[0]}_SYMBOL_DIR"
        self.env_var_name_fp_lib = f"KICAD{self.kicad_version[0]}_FOOTPRINT_DIR"

        self.get_pcb_file_name_from_dir()
        self.get_dru_file_name_from_dir()
        self.fab_dir = self.path / self.relative_fab_path
        self.doc_dir = self.path / self.relative_doc_path
        self.step_model3d_dir = self.path / self.relative_step_model3d_path
        self.lib_dir = self.path / self.relative_lib_path
        self.fp_lib_dir = self.path / self.relative_lib_path / f"{self.project_name}-{self.relative_fp_lib_path}"
        self.model_3d_lib_dir = self.path / self.relative_lib_path / self.relative_3d_model_path

    def get_pcb_file_name_from_dir(self) -> None:
        """Get .kicad_pcb file name from directory `dir`"""

        if len(self.pcb) == 0:
            if not self.disable_logging:
                log.error("No .kicad_pcb file detected.")
            self.pcb_file = ""
            return

        if os.path.exists(self.project_name + ".kicad_pcb"):
            self.pcb_file = self.project_name + ".kicad_pcb"
        else:
            self.pcb_file = self.pcb[0]

        if len(self.pcb) > 1:
            log.warning(f"More than 1 .kicad_pcb file detected. Using {self.pcb_file}")

    def get_dru_file_name_from_dir(self) -> None:
        """Get .kicad_dru file name from directory `dir`"""

        found_dru_files = list(self.path.glob(self.dru_ext))

        if len(found_dru_files) > 1:
            log.error("More than 1 .kicad_dru file detected. Exit.")
            sys.exit(1)
        elif len(found_dru_files) == 1:
            self.dru_file = found_dru_files[0]

    def create_doc_dir(self) -> None:
        assert self.doc_dir != "", "doc dir cannot be empty"
        os.makedirs(self.doc_dir, exist_ok=True)

    def create_fab_dir(self) -> None:
        assert self.fab_dir != "", "fab dir cannot be empty"
        os.makedirs(self.fab_dir, exist_ok=True)

    def create_step_model3d_dir(self) -> None:
        assert self.step_model3d_dir != "", "step_model3d dir cannot be empty"
        os.makedirs(self.step_model3d_dir, exist_ok=True)

    def create_lib_dir(self) -> None:
        assert self.lib_dir != "", "lib dir cannot be empty"
        os.makedirs(self.lib_dir, exist_ok=True)

    def create_fp_lib_dir(self) -> None:
        assert self.fp_lib_dir != "", "fp lib dir cannot be empty"
        os.makedirs(self.fp_lib_dir, exist_ok=True)

    def create_3d_model_lib_dir(self) -> None:
        assert self.model_3d_lib_dir != "", "3d model lib dir cannot be empty"
        os.makedirs(self.model_3d_lib_dir, exist_ok=True)

    def read_lib_table_file(self, name: str, global_lib: str) -> LibraryTable:
        if os.path.exists(name):
            log.debug(f"Using config from {name}")
            return LibraryTable.from_file(name)
        if os.path.exists(global_lib):
            log.warning(f"Provided lib table ({name}) doesn't exist. Using global lib table")
            return LibraryTable.from_file(global_lib)
        log.error("Provided lib table doesn't exist and couldn't find global lib table")
        exit(1)

    def load_kicad_environ_vars(self) -> None:
        if os.path.exists(self.comm_cfg_path):
            with open(self.comm_cfg_path, encoding="utf-8") as kicad_conf:
                cfg = json.load(kicad_conf)
                cfg_env = cfg.get("environment", None)
                cfg_vars = cfg_env.get("vars") if cfg_env and cfg_env.get("vars", None) else {}
                for envvar, val in cfg_vars.items():
                    os.environ[envvar] = val
        else:
            log.warning(f"KiCad Common file ({self.comm_cfg_path}) not found. Using default environment values.")
        os.environ.setdefault(self.env_var_name_sym_lib, "/usr/share/kicad/symbols")
        os.environ.setdefault(self.env_var_name_fp_lib, "/usr/share/kicad/footprints")
        os.environ["KIPRJMOD"] = os.path.abspath(".")
