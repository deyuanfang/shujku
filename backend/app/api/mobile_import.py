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
    """Detect the machine's LAN IP address — try multiple methods."""
    import socket
    # Method 1: connect to external address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    # Method 2: gethostbyname
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    # Method 3: ifconfig approach
    try:
        import subprocess, re
        out = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5).stdout
        for match in re.finditer(r"IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", out):
            ip = match.group(1)
            if not ip.startswith("127.") and ip != "0.0.0.0":
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
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no,viewport-fit=cover">
<title>PersonalKB</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,system-ui,sans-serif;background:#0a0a14;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.card{background:#111827;border-radius:20px;padding:32px 24px;text-align:center;max-width:360px;width:100%;border:1px solid #1f2937}
h1{font-size:20px;margin-bottom:8px}.sub{color:#9ca3af;font-size:14px;margin-bottom:24px}
</style></head><body><div class="card">
<h1>⏰ 会话已过期</h1><p class="sub">请在桌面端重新生成二维码</p>
</div></body></html>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no,maximum-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>PersonalKB · 导入</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a14;color:#e2e8f0;min-height:100vh;padding:12px;padding-bottom:env(safe-area-inset-bottom,20px)}}
.header{{text-align:center;padding:16px 0 12px}}
.header h1{{font-size:18px;font-weight:700;background:linear-gradient(135deg,#818cf8,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}}
.header p{{color:#6b7280;font-size:11px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}}
.card{{background:#111827;border-radius:16px;padding:16px 12px;border:1px solid #1f2937;text-align:center;cursor:pointer;transition:all .15s;display:flex;flex-direction:column;align-items:center;gap:8px}}
.card:active{{background:#1e293b;border-color:#6366f1;transform:scale(.98)}}
.card .icon{{font-size:28px;width:44px;height:44px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px}}
.card .label{{font-size:12px;font-weight:600;color:#d1d5db}}
.card .hint{{font-size:10px;color:#6b7280}}
.icon-purple{{background:rgba(99,102,241,.15);color:#818cf8}}
.icon-pink{{background:rgba(236,72,153,.15);color:#f472b6}}
.icon-amber{{background:rgba(245,158,11,.15);color:#fbbf24}}
.icon-emerald{{background:rgba(16,185,129,.15);color:#34d399}}
.icon-cyan{{background:rgba(6,182,212,.15);color:#22d3ee}}
.icon-red{{background:rgba(239,68,68,.15);color:#f87171}}
.full-card{{background:#111827;border-radius:16px;padding:16px;border:1px solid #1f2937;margin-bottom:8px}}
.full-card h3{{font-size:13px;color:#d1d5db;margin-bottom:8px}}
textarea{{width:100%;min-height:80px;background:#0a0a14;border:1px solid #1f2937;border-radius:12px;padding:12px;color:#e2e8f0;font-size:14px;resize:none;font-family:inherit}}
textarea:focus{{outline:none;border-color:#6366f1}}
input[type=text]{{width:100%;background:#0a0a14;border:1px solid #1f2937;border-radius:12px;padding:10px 12px;color:#e2e8f0;font-size:14px;margin-bottom:6px;font-family:inherit}}
input[type=text]:focus{{outline:none;border-color:#6366f1}}
input[type=file]{{display:none}}
.btn{{display:block;width:100%;padding:14px;border:none;border-radius:14px;font-size:15px;font-weight:600;cursor:pointer;transition:all .15s;margin-top:6px;text-align:center}}
.btn:active{{transform:scale(.97)}}
.btn-primary{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff}}
.btn-recording{{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.7}}}}
.btn-outline{{background:transparent;border:1.5px solid #374151;color:#9ca3af;font-size:13px;padding:10px}}
.toast{{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;z-index:99;display:none;pointer-events:none;box-shadow:0 4px 20px rgba(16,185,129,.3)}}
.toast.error{{background:#ef4444}}
.preview{{margin-top:8px;padding:12px;background:#0a0a14;border-radius:12px;font-size:13px;color:#9ca3af;max-height:120px;overflow-y:auto;white-space:pre-wrap;display:none}}
.rec-status{{text-align:center;font-size:11px;color:#6b7280;margin-top:4px;display:none}}
</style></head><body>
<div class="header"><h1>📡 PersonalKB</h1><p>手机知识导入</p></div>
<div id="toast" class="toast"></div>

<!-- Action grid -->
<div class="grid">
<div class="card" onclick="document.getElementById('fileInput').click()">
  <div class="icon icon-purple">📎</div><div class="label">文件上传</div><div class="hint">文档/PDF/图片</div>
  <input type="file" id="fileInput" multiple onchange="uploadFiles(this.files)" accept=".txt,.md,.pdf,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav,.m4a,.mp4,.mov">
</div>
<div class="card" onclick="document.getElementById('photoInput').click()">
  <div class="icon icon-pink">📷</div><div class="label">拍照上传</div><div class="hint">拍照或选图</div>
  <input type="file" id="photoInput" capture="environment" accept="image/*" multiple onchange="uploadFiles(this.files)">
</div>
<div class="card" id="recordBtn" onclick="toggleRecord()">
  <div class="icon icon-red" id="recIcon">🎤</div><div class="label" id="recLabel">录音</div><div class="hint" id="recHint">点击开始</div>
</div>
<div class="card" onclick="document.getElementById('audioInput').click()">
  <div class="icon icon-amber">🎵</div><div class="label">音频文件</div><div class="hint">MP3/WAV等</div>
  <input type="file" id="audioInput" accept="audio/*" multiple onchange="uploadFiles(this.files)">
</div>
</div>

<!-- Quick note -->
<div class="full-card">
<h3>📝 快速笔记</h3>
<input type="text" id="titleInput" placeholder="标题 (可选)">
<textarea id="noteInput" placeholder="输入内容..."></textarea>
<button class="btn btn-primary" onclick="sendNote()">发送到知识库</button>
</div>

<!-- Recording status -->
<div class="rec-status" id="recStatus">🔴 录音中... <span id="recTimer">00:00</span></div>
<div class="preview" id="preview"></div>

<script>
const API='/api/v1/mobile/import/{session_id}';
const FILES_API='/api/v1/mobile/import-files/{session_id}';
let mediaRecorder=null,recording=false,recTimer=null,recSeconds=0;

function toast(m,e){{const t=document.getElementById('toast');t.textContent=m;t.className='toast'+(e?' error':'');t.style.display='block';setTimeout(()=>t.style.display='none',2000)}}

async function sendNote(){{
  const t=document.getElementById('noteInput').value.trim();
  if(!t)return toast('请输入内容',1);
  const ti=document.getElementById('titleInput').value.trim();
  const f=new FormData();f.append('text',t);f.append('title',ti);f.append('content_type','note');
  try{{const r=await fetch(API,{{method:'POST',body:f}});const d=await r.json();
    if(d.status==='ok'){{document.getElementById('noteInput').value='';document.getElementById('titleInput').value='';toast('已保存')}}
    else if(d.status==='duplicate')toast('已存在');else toast(d.message||'失败',1)
  }}catch(e){{toast('网络错误',1)}}
}}

async function uploadFiles(files){{
  if(!files||files.length===0)return;
  const f=new FormData();
  for(const file of files)f.append('files',file);
  toast('上传中...');
  try{{const r=await fetch(FILES_API,{{method:'POST',body:f}});const d=await r.json();
    if(d.status==='ok')toast('已导入 '+d.imported+'/'+d.total+' 个文件');
    else toast(d.message||'失败',1)
  }}catch(e){{toast('上传失败',1)}}
}}

// Voice recording
async function toggleRecord(){{
  if(recording){{stopRecord();return}}
  try{{
    const stream=await navigator.mediaDevices.getUserMedia({{audio:true}});
    mediaRecorder=new MediaRecorder(stream,{{mimeType:'audio/webm'}});
    const chunks=[];
    mediaRecorder.ondataavailable=e=>{{if(e.data.size>0)chunks.push(e.data)}};
    mediaRecorder.onstop=async()=>{{
      stream.getTracks().forEach(t=>t.stop());
      const blob=new Blob(chunks,{{type:'audio/webm'}});
      const f=new FormData();f.append('files',blob,'recording_'+new Date().toISOString().slice(0,19)+'.webm');
      try{{const r=await fetch(FILES_API,{{method:'POST',body:f}});const d=await r.json();
        if(d.status==='ok')toast('录音已导入');
      }}catch(e){{toast('上传失败',1)}}
    }};
    mediaRecorder.start(1000);
    recording=true;recSeconds=0;
    document.getElementById('recIcon').textContent='⏹';
    document.getElementById('recLabel').textContent='停止';
    document.getElementById('recHint').textContent='录音中...';
    document.getElementById('recStatus').style.display='block';
    document.getElementById('recordBtn').classList.add('btn-recording');
    recTimer=setInterval(()=>{{recSeconds++;document.getElementById('recTimer').textContent=new Date(recSeconds*1000).toISOString().slice(14,19)}},1000);
  }}catch(e){{toast('麦克风权限被拒绝',1)}}
}}

function stopRecord(){{
  if(mediaRecorder&&mediaRecorder.state!=='inactive')mediaRecorder.stop();
  recording=false;clearInterval(recTimer);
  document.getElementById('recIcon').textContent='🎤';
  document.getElementById('recLabel').textContent='录音';
  document.getElementById('recHint').textContent='点击开始';
  document.getElementById('recStatus').style.display='none';
  document.getElementById('recordBtn').classList.remove('btn-recording');
}}
</script></body></html>"""
