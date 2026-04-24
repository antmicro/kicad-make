"""KiCad project class"""

import json
import logging
import os
import subprocess
from pathlib import Path

from askiff import Project
from platformdirs import PlatformDirs

from .kmake_helper import get_kicad_cli_command

log = logging.getLogger(__name__)


class KicadProject(Project):
    """Represents Lazy Loaded KiCad files, with custom, kmake specific folder definitions"""

    relative_lib_path: str = "lib"
    relative_fp_lib_path: str = "footprints"
    relative_3d_model_path: str = "3d-models"
    local_share_path: Path = Path(os.path.expandvars("$HOME/.local/share"))

    system_fp_lib_table = Path("/usr/share/kicad/template/fp-lib-table")
    system_sym_lib_table = Path("/usr/share/kicad/template/sym-lib-table")

    fab_dir: Path
    doc_dir: Path
    step_model3d_dir: Path
    lib_dir: Path
    fp_lib_dir: Path
    model_3d_lib_dir: Path

    def __init__(self, fs_path: Path | None = None, local_share_path: Path | None = None) -> None:
        Project.__init__(self, fs_path=fs_path or Path.cwd())
        self.load()
        if local_share_path is not None:
            self.local_share_path = Path(local_share_path)

        # Get KiCad version
        kicad_cli_name = get_kicad_cli_command()[0]
        self.kicad_version_full = subprocess.run(
            [kicad_cli_name, "--version"], text=True, check=True, capture_output=True
        ).stdout.strip()
        self.kicad_version = ".".join(self.kicad_version_full.split(".")[0:2])

        kicad_cfg_dir = PlatformDirs("kicad", "kicad").user_config_path
        self.comm_cfg_path = Path(kicad_cfg_dir / self.kicad_version / "kicad_common.json")
        self.glob_fp_lib_table_path = Path(kicad_cfg_dir / self.kicad_version / "fp-lib-table")
        self.glob_sym_lib_table_path = Path(kicad_cfg_dir / self.kicad_version / "sym-lib-table")

        self.env_var_name_sym_lib = f"KICAD{self.kicad_version[0]}_SYMBOL_DIR"
        self.env_var_name_fp_lib = f"KICAD{self.kicad_version[0]}_FOOTPRINT_DIR"

        self.fab_dir = self.fs_path / "fab"
        self.doc_dir = self.fs_path / "doc"
        self.step_model3d_dir = self.fs_path / "3d-model"
        self.lib_dir = self.fs_path / self.relative_lib_path
        self.fp_lib_dir = self.fs_path / self.relative_lib_path / f"{self.project_name}-{self.relative_fp_lib_path}"
        self.model_3d_lib_dir = self.fs_path / self.relative_lib_path / self.relative_3d_model_path

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
