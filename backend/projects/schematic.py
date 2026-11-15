"""검증된 KiCad 원본 회로도를 PDF로 변환하는 격리 실행기."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

COMMAND_TIMEOUT_SECONDS = 30
KICAD_CLI = os.getenv("KICAD_CLI", "kicad-cli")


class InvalidKicadProject(ValueError):
    """KiCad PDF 변환 결과가 유효하지 않다."""


class KicadServiceUnavailable(RuntimeError):
    """KiCad CLI를 실행할 수 없거나 제한 시간 안에 끝나지 않았다."""


def run_kicad_pdf(root: Path, output: Path) -> tuple[str, Path]:
    return _run_export(root, output, 'pdf')


def run_kicad_netlist(root: Path, output: Path) -> Path:
    return _run_export(root, output, 'netlist')[1]


def _run_export(root: Path, output: Path, kind: str) -> tuple[str, Path]:
    """검증한 root 회로도와 자식 시트를 한 PDF로 내보낸다."""
    pdf = output / ('schematic.net' if kind == 'netlist' else 'schematic.pdf')
    home = output / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", os.defpath)}
    try:
        version = subprocess.run(
            [KICAD_CLI, "--version"], check=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, env=env,
        ).stdout.strip()
        command = [KICAD_CLI, "sch", "export", kind, "--output", str(pdf)]
        if kind == 'netlist':
            command += ['--format', 'kicadsexpr']
        command.append(str(root))
        if os.name == "posix":
            command = ["prlimit", "--as=2147483648", '--fsize='+str(5*1024**2 if kind == 'netlist' else 20*1024**2), "--", *command]
        subprocess.run(command, cwd=root.parent, check=True, env=env,
                       timeout=COMMAND_TIMEOUT_SECONDS, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        raise KicadServiceUnavailable("KiCad 변환 서비스를 사용할 수 없습니다.") from None
    except subprocess.CalledProcessError:
        raise InvalidKicadProject("KiCad PDF를 변환할 수 없습니다.") from None
    return version, pdf
