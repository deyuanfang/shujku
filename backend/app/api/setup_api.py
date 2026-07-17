"""Setup API — check and auto-install tools."""

from fastapi import APIRouter
from app.services.auto_setup import check_all_tools, auto_install_missing

router = APIRouter()


@router.get("/setup/check")
async def check_tools():
    """Check which tools are installed and which are missing."""
    report = await check_all_tools()
    return {
        "all_ok": report.all_ok,
        "tools": [
            {
                "name": t.name,
                "category": t.category,
                "installed": t.installed,
                "version": t.version,
                "auto_installable": t.auto_installable,
                "install_cmd": t.install_cmd,
            }
            for t in report.tools
        ],
    }


@router.post("/setup/install")
async def install_missing():
    """Auto-install all missing Python packages."""
    report = await check_all_tools()
    if report.all_ok:
        return {"status": "ok", "message": "所有工具已就绪", "actions": []}

    report = await auto_install_missing(report)
    return {
        "status": "ok",
        "actions": report.actions_taken,
        "remaining_missing": [
            t.name for t in report.tools if not t.installed
        ],
    }
