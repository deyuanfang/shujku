"""Mobile Import API — QR code remote import and phone-to-desktop bridge.

Allows importing knowledge from a phone by:
1. Scanning a QR code → opens a mobile web page
2. Pasting text/notes/links directly from phone browser
3. Uploading files from phone to the knowledge base
"""

import io
import uuid
import json
import time
import base64
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.connection import get_db
from app.database.models import Document, Category
from app.services.nlp_pipeline import nlp_pipeline
from app.utils.hash_utils import compute_text_hash

logger = logging.getLogger(__name__)
router = APIRouter()

# Active mobile sessions: {session_id: {created_at, ip, count}}
_sessions: dict[str, dict] = {}

SESSION_TIMEOUT_MINUTES = 30


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_lan_ip() -> str:
    """Detect the machine's LAN IP address."""
    import socket
    try:
        # Connect to an external address to determine the active network interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass
    # Fallback: iterate interfaces
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


def _cleanup_sessions():
    """Remove expired sessions."""
    now = time.time()
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.get("_ts", 0) > SESSION_TIMEOUT_MINUTES * 60
    ]
    for sid in expired:
        del _sessions[sid]


# ── Session Management ─────────────────────────────

@router.post("/mobile/session")
async def create_mobile_session(request: Request):
    """Create a new mobile import session. Returns session info with QR content."""
    _cleanup_sessions()

    session_id = str(uuid.uuid4())[:12]

    # Use LAN IP for phone accessibility (not 127.0.0.1)
    lan_ip = _get_lan_ip()
    port = request.url.port or 18765
    mobile_url = f"http://{lan_ip}:{port}/api/v1/mobile/import-page/{session_id}"
    local_url = f"http://127.0.0.1:{port}/api/v1/mobile/import-page/{session_id}"

    _sessions[session_id] = {
        "id": session_id,
        "created_at": _now(),
        "import_count": 0,
        "ip": request.client.host if request.client else "unknown",
        "_ts": time.time(),
    }

    # Generate QR code
    qr_base64 = _generate_qr(mobile_url)

    return {
        "session_id": session_id,
        "lan_ip": lan_ip,
        "port": port,
        "mobile_url": mobile_url,
        "local_url": local_url,
        "qr_code": qr_base64,
        "expires_in_minutes": SESSION_TIMEOUT_MINUTES,
        "tip": "手机和电脑连同一WiFi，扫描二维码即可打开" if lan_ip != "127.0.0.1" else "未检测到局域网IP，请手动输入链接",
    }


@router.get("/mobile/session/{session_id}")
async def get_session_status(session_id: str):
    """Check session status and import count."""
    session = _sessions.get(session_id)
    if not session:
        return {"status": "expired", "message": "会话已过期，请重新生成二维码"}
    return {
        "status": "active",
        "session_id": session_id,
        "import_count": session.get("import_count", 0),
        "created_at": session.get("created_at"),
    }


# ── Mobile Web Page ───────────────────────────────

@router.get("/mobile/import-page/{session_id}", response_class=HTMLResponse)
async def mobile_import_page(session_id: str):
    """Lightweight mobile-friendly page for importing content from phone."""
    if session_id not in _sessions:
        return HTMLResponse(_page_html("expired", "会话已过期"), status_code=410)

    return HTMLResponse(_page_html(session_id, "active"))


# ── Mobile Import Actions ─────────────────────────

@router.post("/mobile/import/{session_id}")
async def mobile_import(
    session_id: str,
    text: str = Form(...),
    title: Optional[str] = Form(None),
    content_type: str = Form("note"),
    db: AsyncSession = Depends(get_db),
):
    """Import text/note from mobile device."""
    if session_id not in _sessions:
        return JSONResponse({"status": "expired", "message": "会话已过期"}, status_code=410)

    # Import the content
    result = await _import_text(db, text, title or "", content_type)

    # Update session
    _sessions[session_id]["import_count"] = _sessions[session_id].get("import_count", 0) + 1
    _sessions[session_id]["_ts"] = time.time()

    return {
        "status": "ok",
        "document_id": result["document_id"],
        "title": result["title"],
        "category": result["category"],
        "keywords": result["keywords"],
        "import_count": _sessions[session_id]["import_count"],
    }


@router.post("/mobile/import-file/{session_id}")
async def mobile_import_file(
    session_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import a file from mobile device."""
    if session_id not in _sessions:
        return JSONResponse({"status": "expired", "message": "会话已过期"}, status_code=410)

    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    result = await _import_text(
        db, text,
        title=file.filename or "手机上传",
        content_type="text",
    )

    _sessions[session_id]["import_count"] = _sessions[session_id].get("import_count", 0) + 1
    _sessions[session_id]["_ts"] = time.time()

    return {
        "status": "ok",
        "document_id": result["document_id"],
        "title": result["title"],
        "filename": file.filename,
        "size_bytes": len(content),
        "import_count": _sessions[session_id]["import_count"],
    }


@router.post("/mobile/import-files/{session_id}")
async def mobile_import_files(
    session_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import multiple files from mobile device at once."""
    if session_id not in _sessions:
        return JSONResponse({"status": "expired", "message": "会话已过期"}, status_code=410)

    results = []
    for file in files:
        try:
            content = await file.read()
            text = content.decode("utf-8", errors="replace")
            result = await _import_text(
                db, text,
                title=file.filename or "手机上传",
                content_type="text",
            )
            results.append({
                "filename": file.filename,
                "status": result["status"],
                "document_id": result["document_id"],
                "title": result["title"],
                "size_bytes": len(content),
            })
            _sessions[session_id]["import_count"] = _sessions[session_id].get("import_count", 0) + 1
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "error": str(e)})

    _sessions[session_id]["_ts"] = time.time()

    return {
        "status": "ok",
        "imported": len([r for r in results if r["status"] == "ok"]),
        "total": len(files),
        "import_count": _sessions[session_id]["import_count"],
        "files": results,
    }


# ── Batch sync from phone ─────────────────────────

@router.post("/mobile/sync/{session_id}")
async def mobile_batch_sync(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Batch sync multiple items from phone at once."""
    if session_id not in _sessions:
        return JSONResponse({"status": "expired"}, status_code=410)

    try:
        body = await request.json()
        items = body.get("items", [])
    except Exception as e:
        # Try parsing raw body
        try:
            raw = await request.body()
            body = json.loads(raw.decode("utf-8"))
            items = body.get("items", [])
        except Exception:
            return JSONResponse({"status": "error", "message": f"无效的请求格式: {str(e)}"}, status_code=400)

    if not items:
        return {"status": "ok", "imported": 0, "items": []}

    results = []
    for item in items[:20]:  # Max 20 per batch
        result = await _import_text(
            db,
            text=item.get("text", ""),
            title=item.get("title", ""),
            content_type=item.get("type", "note"),
        )
        results.append(result)
        _sessions[session_id]["import_count"] = _sessions[session_id].get("import_count", 0) + 1

    _sessions[session_id]["_ts"] = time.time()

    return {
        "status": "ok",
        "imported": len(results),
        "total_count": _sessions[session_id]["import_count"],
        "items": results,
    }


# ── Internal helpers ──────────────────────────────

async def _import_text(db: AsyncSession, text: str, title: str, content_type: str) -> dict:
    """Import a single text item into the knowledge base."""
    text_hash = compute_text_hash(text)

    # Check duplicate
    result = await db.execute(
        select(Document).where(Document.original_hash == text_hash)
    )
    if (existing := result.scalar_one_or_none()):
        return {
            "status": "duplicate",
            "document_id": existing.id,
            "title": existing.title,
            "category": "",
            "keywords": [],
        }

    # NLP classification
    cat_result = await db.execute(select(Category))
    categories = [{"id": c.id, "name": c.name} for c in cat_result.scalars().all()]
    classification = nlp_pipeline.classify(text, categories)

    if not title:
        title = text[:50] + ("..." if len(text) > 50 else "")

    doc = Document(
        id=str(uuid.uuid4()),
        title=title,
        content_type=content_type,
        original_hash=text_hash,
        raw_text=text,
        word_count=len(text.split()),
        char_count=len(text),
        category_id=classification["category_id"],
        created_at=_now(),
        updated_at=_now(),
        last_analyzed_at=_now(),
        source_path="mobile_import",
    )
    db.add(doc)

    if classification["category_id"]:
        cat_result = await db.execute(
            select(Category).where(Category.id == classification["category_id"])
        )
        if cat := cat_result.scalar_one_or_none():
            cat.document_count += 1

    await db.flush()

    # Enqueue analysis
    from app.services.task_queue import enqueue_analysis
    import asyncio
    asyncio.create_task(enqueue_analysis(doc.id, doc.title, text))

    return {
        "status": "ok",
        "document_id": doc.id,
        "title": doc.title,
        "category": classification["category_name"],
        "keywords": classification["keywords"],
    }


def _generate_qr(url: str) -> str:
    """Generate QR code as base64 PNG."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # Fallback: return a text-based QR approximation (not scannable but shows URL)
        return ""


# ── Mobile-friendly HTML page ─────────────────────

def _page_html(session_id: str, status: str) -> str:
    if status == "expired":
        return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>PersonalKB</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.card{background:#1e293b;border-radius:16px;padding:32px 24px;text-align:center;max-width:360px;width:100%}
h1{font-size:20px;margin-bottom:8px}.sub{color:#94a3b8;font-size:14px;margin-bottom:24px}
.btn{display:inline-block;background:#6366f1;color:#fff;border:none;padding:12px 24px;border-radius:10px;font-size:16px;text-decoration:none}
</style></head><body><div class="card">
<h1>⏰ 会话已过期</h1><p class="sub">请重新扫描 PersonalKB 桌面端的二维码</p>
</div></body></html>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no,maximum-scale=1">
<title>PersonalKB · 手机导入</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding:16px}}
.header{{text-align:center;padding:12px 0 20px}}
.header h1{{font-size:20px;font-weight:700;background:linear-gradient(135deg,#818cf8,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header p{{color:#64748b;font-size:13px;margin-top:4px}}
.card{{background:#1e293b;border-radius:16px;padding:20px;margin-bottom:12px;border:1px solid #334155}}
.card h2{{font-size:15px;margin-bottom:12px;color:#cbd5e1}}
textarea{{width:100%;min-height:120px;background:#0f172a;border:1px solid #334155;border-radius:10px;padding:12px;color:#e2e8f0;font-size:15px;resize:vertical;font-family:inherit}}
textarea:focus{{outline:none;border-color:#6366f1}}
input[type=text]{{width:100%;background:#0f172a;border:1px solid #334155;border-radius:10px;padding:10px 12px;color:#e2e8f0;font-size:15px;margin-bottom:8px;font-family:inherit}}
input[type=text]:focus{{outline:none;border-color:#6366f1}}
input[type=file]{{display:none}}
.btn{{display:block;width:100%;padding:14px;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;transition:all .2s;margin-top:8px}}
.btn-primary{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff}}
.btn-primary:active{{transform:scale(.98);opacity:.9}}
.btn-outline{{background:transparent;border:1.5px solid #334155;color:#94a3b8;font-size:14px;padding:12px}}
.btn-outline:active{{background:#1e293b}}
.toast{{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:10px 20px;border-radius:20px;font-size:14px;z-index:99;display:none;box-shadow:0 4px 20px rgba(16,185,129,.3)}}
.toast.error{{background:#ef4444;box-shadow:0 4px 20px rgba(239,68,68,.3)}}
.stats{{display:flex;gap:12px;margin-top:16px}}
.stat{{flex:1;background:#0f172a;border-radius:10px;padding:12px;text-align:center}}
.stat .num{{font-size:24px;font-weight:700;color:#818cf8}}
.stat .lbl{{font-size:11px;color:#64748b;margin-top:2px}}
</style></head><body>
<div class="header"><h1>📡 PersonalKB</h1><p>手机知识导入 · 扫描二维码连接</p></div>
<div id="toast" class="toast"></div>

<div class="card">
<h2>📝 快速笔记</h2>
<input type="text" id="title" placeholder="标题 (可选)">
<textarea id="text" placeholder="在这里粘贴或输入内容..."></textarea>
<button class="btn btn-primary" onclick="sendNote()">发送到知识库</button>
</div>

<div class="card">
<h2>📎 文件上传 (支持多选)</h2>
<button class="btn btn-outline" onclick="document.getElementById('files').click()">选择文件 (.txt/.md/.pdf/.jpg)</button>
<input type="file" id="files" multiple onchange="sendFiles()" accept=".txt,.md,.pdf,.jpg,.jpeg,.png" style="display:none">
</div>

<div class="card">
<h2>🔗 快速链接</h2>
<input type="text" id="url" placeholder="粘贴网页链接...">
<button class="btn btn-primary" onclick="sendURL()">抓取网页内容</button>
</div>

<div class="stats">
<div class="stat"><div class="num" id="count">0</div><div class="lbl">本次导入</div></div>
<div class="stat"><div class="num" id="total">-</div><div class="lbl">知识库总计</div></div>
</div>

<script>
const API = '/api/v1/mobile/import/{session_id}';
const MULTI_FILE_API = '/api/v1/mobile/import-files/{session_id}';
let importCount = 0;

function toast(msg, isError) {{
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (isError ? ' error' : '');
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 2500);
}}

async function sendNote() {{
  const text = document.getElementById('text').value.trim();
  if (!text) return toast('请输入内容', true);
  const title = document.getElementById('title').value.trim();
  const form = new FormData();
  form.append('text', text); form.append('title', title); form.append('content_type', 'note');
  try {{
    const r = await fetch(API, {{method:'POST',body:form}});
    const d = await r.json();
    if (d.status === 'ok') {{
      importCount++; document.getElementById('count').textContent = importCount;
      document.getElementById('text').value = ''; document.getElementById('title').value = '';
      toast('已保存: ' + (d.category || '未分类'));
    }} else if (d.status === 'duplicate') {{
      toast('内容已存在');
    }} else {{
      toast(d.message || '失败', true);
    }}
  }} catch(e) {{ toast('网络错误', true); }}
}}

async function sendFiles() {{
  const input = document.getElementById('files');
  const fileList = input.files;
  if (!fileList || fileList.length === 0) return;

  const form = new FormData();
  for (const file of fileList) {{
    form.append('files', file);
  }}

  toast('正在上传 ' + fileList.length + ' 个文件...');
  try {{
    const r = await fetch(MULTI_FILE_API, {{method:'POST',body:form}});
    const d = await r.json();
    if (d.status === 'ok') {{
      importCount += d.imported;
      document.getElementById('count').textContent = importCount;
      input.value = '';
      if (d.files) {{
        const names = d.files.filter(f => f.status === 'ok').map(f => f.filename).join(', ');
        toast('已导入 ' + d.imported + '/' + d.total + ' 个文件: ' + (names || ''));
      }}
      if (d.imported < d.total) {{
        const errors = d.files.filter(f => f.status !== 'ok').map(f => f.filename + '(' + f.error + ')').join('; ');
        if (errors) setTimeout(() => toast('失败: ' + errors, true), 3000);
      }}
    }} else toast(d.message || '失败', true);
  }} catch(e) {{ toast('网络错误', true); }}
}}

async function sendURL() {{
  const url = document.getElementById('url').value.trim();
  if (!url) return toast('请输入链接', true);
  const form = new FormData();
  form.append('text', url); form.append('title', url); form.append('content_type', 'url');
  try {{
    const r = await fetch(API, {{method:'POST',body:form}});
    const d = await r.json();
    if (d.status === 'ok') {{
      importCount++; document.getElementById('count').textContent = importCount;
      document.getElementById('url').value = '';
      toast('链接已保存');
    }} else toast(d.message || '失败', true);
  }} catch(e) {{ toast('网络错误', true); }}
}}

// Fetch total doc count
fetch('/api/v1/stats').then(r=>r.json()).then(d=>{{
  document.getElementById('total').textContent = d.total_documents || 0;
}});
</script></body></html>"""
