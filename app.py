import os
import uuid
import json
import time
from datetime import datetime, timedelta
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from threading import Thread

app = FastAPI()

DATA_DIR = "/usr/share/nginx/html/data"
os.makedirs(DATA_DIR, exist_ok=True)
META_FILE = os.path.join(DATA_DIR, "meta.json")
ADMIN_SECRET = "superadmin2026"

def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r") as f:
            return json.load(f)
    return {}

def save_meta(data):
    with open(META_FILE, "w") as f:
        json.dump(data, f)

def cleanup_old_files():
    while True:
        data = load_meta()
        now = datetime.now()
        to_delete = []
        for uid, info in data.items():
            if info.get("expires_at") != "never":
                exp_date = datetime.fromisoformat(info["expires_at"])
                if now > exp_date:
                    to_delete.append(uid)
        
        for uid in to_delete:
            file_path = os.path.join(DATA_DIR, info["filename"])
            if os.path.exists(file_path):
                os.remove(file_path)
            del data[uid]
        
        if to_delete:
            save_meta(data)
        time.sleep(3600)

Thread(target=cleanup_old_files, daemon=True).start()

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), days: int = Form(2)):
    uid = str(uuid.uuid4())
    safe_filename = uid + "_" + file.filename
    save_path = os.path.join(DATA_DIR, safe_filename)
    
    with open(save_path, "wb") as f:
        f.write(await file.read())
        
    expires_at = "never" if days > 7 else (datetime.now() + timedelta(days=days)).isoformat()
    
    meta = load_meta()
    meta[uid] = {
        "original_name": file.filename,
        "filename": safe_filename,
        "upload_time": datetime.now().isoformat(),
        "expires_at": expires_at,
        "size": os.path.getsize(save_path)
    }
    save_meta(meta)
    return {"url": f"/download.html?id={uid}"}

@app.get("/api/info/{uid}")
async def get_file_info(uid: str):
    meta = load_meta()
    if uid not in meta:
        raise HTTPException(status_code=404, detail="File not found or expired.")
    info = meta[uid]
    return {
        "original_name": info["original_name"],
        "size": info["size"],
        "expires_at": info["expires_at"]
    }

@app.get("/api/download/{uid}")
async def download_file(uid: str):
    meta = load_meta()
    if uid not in meta:
        raise HTTPException(status_code=404, detail="File not found or expired.")
    
    info = meta[uid]
    file_path = os.path.join(DATA_DIR, info["filename"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing.")
        
    return FileResponse(path=file_path, filename=info["original_name"])

@app.get("/api/admin/verify")
async def admin_verify(token: str = Query(None)):
    if token != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"status": "ok"}

@app.get("/api/admin/list")
async def admin_list(token: str = Query(None)):
    if token != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    return load_meta()

@app.delete("/api/admin/delete/{uid}")
async def admin_delete(uid: str, token: str = Query(None)):
    if token != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    meta = load_meta()
    if uid in meta:
        file_path = os.path.join(DATA_DIR, meta[uid]["filename"])
        if os.path.exists(file_path):
            os.remove(file_path)
        del meta[uid]
        save_meta(meta)
        return {"status": "success"}
    raise HTTPException(status_code=404)

@app.get("/download.html", response_class=HTMLResponse)
async def serve_download():
    return FileResponse("static/download.html")

@app.get("/manage.html", response_class=HTMLResponse)
async def serve_manage():
    return FileResponse("static/manage.html")

@app.get("/dashboard.html", response_class=HTMLResponse)
async def serve_dashboard():
    return FileResponse("static/dashboard.html")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
