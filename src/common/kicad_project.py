"""KiCad project class"""

import os

import sys
import logging
import typing
import subprocess
from pathlib import Path
from typing import List

from kiutils.symbol import SymbolLib
from kiutils.footprint import Footprint

from .kmake_helper import find_files_by_ext, KICAD_CLI_NAME

log = logging.getLogger(__name__)


class KicadProject:
    sch_ext: str = "kicad_sch"
    pro_ext: str = "kicad_pro"
    pcb_ext: str = "kicad_pcb"
    dru_ext: str = "kciad_dru"
    sym_lib_ext: str = "kicad_sym"
    fp_lib_ext: str = "kicad_mod"
    vrml_ext: str = "vrml"
    relative_fab_path: str = "fab"
    relative_doc_path: str = "doc"
    relative_step_model3d_path: str = "3d-model"
    relative_vrml_model3d_path: str = "3d-model"
    relative_vrml_shapes3d_path: str = "shapes3d"
    relative_lib_path: str = "lib"
    relative_fp_lib_path: str = "footprints"
    relative_3d_model_path: str = "3d-models"
    local_sym_lib: SymbolLib
    local_fp_lib: typing.List[Footprint]

    def __init__(self, disable_logging: bool = False) -> None:
        """Manage kicad files

        Parameters:
                disable_logging (bool): do not log when no KiCad file exists
        """
        self.disable_logging = disable_logging

        self.pro_file: str = ""
        self.pcb_file: str = ""
        self.all_sch_files: List[str] = []
        self.sch_files: List[str] = []

        self.kicad_version = subprocess.run(
            [KICAD_CLI_NAME, "--version"], text=True, check=True, capture_output=True
        ).stdout
        self.kicad_version = ".".join(self.kicad_version.split(".")[0:2])

        self.comm_cfg_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/kicad_common.json")
        self.glob_fp_lib_table_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/fp-lib-table")
        self.glob_sym_lib_table_path = os.path.expanduser(f"~/.config/kicad/{self.kicad_version}/sym-lib-table")

        self.get_project_dir()
        self.get_pro_file_name_from_dir(self.dir)
        self.get_pcb_file_name_from_dir(self.dir)
        self.get_sch_file_names_from_dir(self.dir)
        self.get_dru_file_name_from_dir(self.dir)
        self.sort_sch_files()
        self.fab_dir = f"{self.dir}/{self.relative_fab_path}"
        self.doc_dir = f"{self.dir}/{self.relative_doc_path}"
        self.vrml_model3d_dir = f"{self.dir}/{self.relative_vrml_model3d_path}"
        self.vrml_shapes3d_dir = f"{self.dir}/{self.relative_vrml_shapes3d_path}"
        self.step_model3d_dir = f"{self.dir}/{self.relative_step_model3d_path}"
        self.lib_dir = f"{self.dir}/{self.relative_lib_path}"
        self.fp_lib_dir = f"{self.dir}/{self.relative_lib_path}/{self.name}-{self.relative_fp_lib_path}"
        self.model_3d_lib_dir = f"{self.dir}/{self.relative_lib_path}/{self.relative_3d_model_path}"

    def sort_sch_files(self) -> None:
        """Sort .kicad_sch, root file on top"""
        self.sch_files.sort(
            key=lambda x: x.rpartition("/")[2].startswith(self.name + "."),
            reverse=True,
        )

    def get_pro_file_name_from_dir(self, _dir: str = "") -> None:
        """Get .kicad_pro file name from directory `dir`"""

        assert _dir != ""
        found_pro_files = []

        found_pro_files = find_files_by_ext(_dir, self.pro_ext, disable_logging=True)

        if len(found_pro_files) == 0:
            if not self.disable_logging:
                log.warning("No .kicad_pro file detected.")
            self.pro_file = ""
            self.name = ""
            return

        if len(found_pro_files) > 1:
            log.warning(f"More than 1 .kicad_pro file detected. Using {found_pro_files[0]}.")

        self.pro_file = found_pro_files[0]
        log.debug("Project file path: %s", self.pro_file)
        self.name = Path(self.pro_file).stem
        log.debug("Project name: %s", self.name)

    def get_pcb_file_name_from_dir(self, _dir: str = "") -> None:
        """Get .kicad_pcb file name from directory `dir`"""

        assert _dir != ""
        found_pcb_files = []

        found_pcb_files = find_files_by_ext(_dir, self.pcb_ext, disable_logging=True)

        if len(found_pcb_files) == 0:
            if not self.disable_logging:
                log.error("No .kicad_pcb file detected. Exit.")
            self.pcb_file = ""
            return

        if os.path.exists(self.name + ".kicad_pcb"):
            self.pcb_file = self.name + ".kicad_pcb"
        else:
            self.pcb_file = found_pcb_files[0]

        if len(found_pcb_files) > 1:
            log.warning(f"More than 1 .kicad_pcb file detected. Using {self.pcb_file}")

    def get_dru_file_name_from_dir(self, _dir: str = "") -> None:
        """Get .kicad_dru file name from directory `dir`"""

        assert _dir != ""
        found_dru_files = []

        found_dru_files = find_files_by_ext(_dir, self.dru_ext, disable_logging=True)

        if len(found_dru_files) > 1:
            log.error("More than 1 .kicad_dru file detected. Exit.")
            sys.exit()
        elif len(found_dru_files) == 1:
            self.dru_file = found_dru_files[0]

    def get_sch_file_names_from_dir(self, _dir: str = "") -> None:
        """Get .kicad_sch file names from directory `dir`

        Also get `sch_root`."""

        assert _dir != ""
        self.all_sch_files = find_files_by_ext(self.dir, self.sch_ext, disable_logging=True)
        self.sch_root = f"{self.name}.{self.sch_ext}"

    def get_project_dir(self) -> None:
        """Get `dir` from current working directory"""
        self.dir = os.getcwd()

    def create_doc_dir(self) -> None:
        assert self.doc_dir != "", "doc dir cannot be empty"
        os.makedirs(self.doc_dir, exist_ok=True)

    def create_fab_dir(self) -> None:
        assert self.fab_dir != "", "fab dir cannot be empty"
        os.makedirs(self.fab_dir, exist_ok=True)

    def create_vrml_model3d_dir(self) -> None:
        assert self.vrml_model3d_dir != "", "vrml_model3d dir cannot be empty"
        os.makedirs(self.vrml_model3d_dir, exist_ok=True)

    def create_step_model3d_dir(self) -> None:
        assert self.step_model3d_dir != "", "step_model3d dir cannot be empty"
        os.makedirs(self.step_model3d_dir, exist_ok=True)

    def create_vrml_shapes3d_dir(self) -> None:
        assert self.vrml_shapes3d_dir != "", "vrml_shapes3d dir cannot be empty"
        os.makedirs(self.vrml_shapes3d_dir, exist_ok=True)

    def create_lib_dir(self) -> None:
        assert self.lib_dir != "", "lib dir cannot be empty"
        os.makedirs(self.lib_dir, exist_ok=True)

    def create_fp_lib_dir(self) -> None:
        assert self.fp_lib_dir != "", "fp lib dir cannot be empty"
        os.makedirs(self.fp_lib_dir, exist_ok=True)

    def create_3d_model_lib_dir(self) -> None:
        assert self.model_3d_lib_dir != "", "3d model lib dir cannot be empty"
        os.makedirs(self.model_3d_lib_dir, exist_ok=True)
