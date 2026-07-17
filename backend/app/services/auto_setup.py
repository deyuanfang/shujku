"""Auto-Setup — automatic dependency detection, download, and installation.

Checks for required tools and auto-installs missing ones.
Supports: pip packages, ffmpeg, tesseract, system tools.
"""

import subprocess
import sys
import os
import shutil
import logging
import asyncio
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ToolStatus:
    name: str
    category: str  # "python", "system", "optional"
    installed: bool = False
    version: str = ""
    path: str = ""
    error: str = ""
    install_cmd: str = ""
    auto_installable: bool = False


@dataclass
class SetupReport:
    all_ok: bool = True
    tools: list[ToolStatus] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)


# ── Tool Registry ──────────────────────────────────

TOOL_REGISTRY = {
    # Python packages (auto-installable via pip)
    "jieba": {
        "name": "jieba (中文分词)", "category": "python", "auto_installable": True,
        "pip_package": "jieba", "import_check": "jieba",
    },
    "sklearn": {
        "name": "scikit-learn (机器学习)", "category": "python", "auto_installable": True,
        "pip_package": "scikit-learn", "import_check": "sklearn",
    },
    "numpy": {
        "name": "NumPy", "category": "python", "auto_installable": True,
        "pip_package": "numpy", "import_check": "numpy",
    },
    "PyMuPDF": {
        "name": "PyMuPDF (PDF解析)", "category": "python", "auto_installable": True,
        "pip_package": "PyMuPDF", "import_check": "fitz",
    },
    "paddleocr": {
        "name": "PaddleOCR (文字识别)", "category": "python", "auto_installable": True,
        "pip_package": "paddleocr", "import_check": "paddleocr",
    },
    "anthropic": {
        "name": "Anthropic SDK (Claude)", "category": "python", "auto_installable": True,
        "pip_package": "anthropic", "import_check": "anthropic",
    },
    "openai": {
        "name": "OpenAI SDK (GPT)", "category": "python", "auto_installable": True,
        "pip_package": "openai", "import_check": "openai",
    },
    "httpx": {
        "name": "httpx (HTTP客户端)", "category": "python", "auto_installable": True,
        "pip_package": "httpx", "import_check": "httpx",
    },
    "bs4": {
        "name": "BeautifulSoup4 (网页解析)", "category": "python", "auto_installable": True,
        "pip_package": "beautifulsoup4", "import_check": "bs4",
    },
    "Pillow": {
        "name": "Pillow (图片处理)", "category": "python", "auto_installable": True,
        "pip_package": "Pillow", "import_check": "PIL",
    },
    "qrcode": {
        "name": "qrcode (二维码)", "category": "python", "auto_installable": True,
        "pip_package": "qrcode[pil]", "import_check": "qrcode",
    },
    # System tools
    "ffmpeg": {
        "name": "FFmpeg (视频处理)", "category": "system", "auto_installable": False,
        "install_cmd": "下载: https://ffmpeg.org/download.html",
    },
    "ffprobe": {
        "name": "FFprobe (视频分析)", "category": "system", "auto_installable": False,
    },
    "tesseract": {
        "name": "Tesseract OCR", "category": "system", "auto_installable": False,
        "install_cmd": "下载: https://github.com/UB-Mannheim/tesseract/wiki",
    },
    "git": {
        "name": "Git", "category": "system", "auto_installable": False,
    },
}


# ── Checker Functions ──────────────────────────────

def _check_python_package(import_name: str) -> tuple[bool, str]:
    """Check if a Python package is importable."""
    try:
        mod = __import__(import_name)
        version = getattr(mod, "__version__", getattr(mod, "VERSION", ""))
        return True, str(version) if version else "installed"
    except ImportError:
        return False, ""


def _check_system_tool(tool_name: str) -> tuple[bool, str]:
    """Check if a system tool is available in PATH."""
    try:
        result = subprocess.run(
            [tool_name, "-version"] if tool_name != "tesseract" else [tool_name, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version_line = (result.stdout or result.stderr).split("\n")[0]
            return True, version_line[:60]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check common install paths on Windows
    if sys.platform == "win32":
        common_paths = {
            "ffmpeg": [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"],
            "ffprobe": [r"C:\ffmpeg\bin\ffprobe.exe", r"C:\Program Files\ffmpeg\bin\ffprobe.exe"],
            "tesseract": [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                          rf"{os.environ.get('LOCALAPPDATA','')}\Tesseract-OCR\tesseract.exe"],
        }
        for path in common_paths.get(tool_name, []):
            if os.path.exists(path):
                return True, path

    return False, ""


# ── Main Check ─────────────────────────────────────

async def check_all_tools() -> SetupReport:
    """Check all registered tools and return a SetupReport."""
    report = SetupReport()

    for tool_id, tool_info in TOOL_REGISTRY.items():
        status = ToolStatus(
            name=tool_info["name"],
            category=tool_info["category"],
            auto_installable=tool_info.get("auto_installable", False),
            install_cmd=tool_info.get("install_cmd", ""),
        )

        if tool_info["category"] == "python":
            ok, version = _check_python_package(tool_info.get("import_check", tool_id))
            status.installed = ok
            status.version = version
        elif tool_info["category"] == "system":
            ok, version = _check_system_tool(tool_id)
            status.installed = ok
            status.version = version
        else:
            status.installed = False

        if not status.installed:
            report.all_ok = False

        report.tools.append(status)

    return report


async def auto_install_missing(report: SetupReport) -> SetupReport:
    """Auto-install missing Python packages via pip."""
    missing_python = [
        t for t in report.tools
        if not t.installed and t.auto_installable and t.category == "python"
    ]

    if not missing_python:
        return report

    packages = []
    for tool_id, info in TOOL_REGISTRY.items():
        for mt in missing_python:
            if mt.name == info["name"] and "pip_package" in info:
                packages.append(info["pip_package"])
                break

    if packages:
        logger.info(f"Auto-installing: {packages}")
        report.actions_taken.append(f"pip install {' '.join(packages)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "-q", *packages,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()

            # Re-check the installed packages
            for mt in missing_python:
                tool_id = None
                for tid, info in TOOL_REGISTRY.items():
                    if info["name"] == mt.name:
                        tool_id = tid
                        break
                if tool_id:
                    ok, version = _check_python_package(
                        TOOL_REGISTRY[tool_id].get("import_check", tool_id)
                    )
                    mt.installed = ok
                    mt.version = version
                    if ok:
                        report.actions_taken.append(f"已安装: {mt.name}")

        except Exception as e:
            logger.error(f"Auto-install failed: {e}")
            report.actions_taken.append(f"安装失败: {e}")

    return report


# ── Quick Bootstrap ────────────────────────────────

async def ensure_core_deps():
    """Ensure absolutely essential deps are installed on startup."""
    core = ["fastapi", "uvicorn", "sqlalchemy", "aiosqlite", "jieba"]
    missing = []
    for pkg in core:
        if pkg == "aiosqlite":
            ok, _ = _check_python_package("aiosqlite")
        else:
            ok, _ = _check_python_package(pkg)
        if not ok:
            missing.append(pkg)

    if missing:
        logger.info(f"Installing core deps: {missing}")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "-q", *missing,
        )
        await proc.wait()
