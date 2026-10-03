import os
import uuid
import json
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from threading import Thread

app = FastAPI()

# K8sのPVCマウント先（YAMLの設定と合わせる）
DATA_DIR = "/usr/share/nginx/html/data"
os.makedirs(DATA_DIR, exist_ok=True)
META_FILE = os.path.join(DATA_DIR, "meta.json")
ADMIN_SECRET = "superadmin2026" # 管理者用シークレットキー

def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r") as f:
            return json.load(f)
    return {}

def save_meta(data):
    with open(META_FILE, "w") as f:
        json.dump(data, f)

# 裏で定期的に期限切れファイルを削除するバッチ処理
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
        time.sleep(3600) # 1時間ごとにチェック

Thread(target=cleanup_old_files, daemon=True).start()

# === API ===
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), days: int = Form(2)):
    uid = str(uuid.uuid4())
    safe_filename = uid + "_" + file.filename
    save_path = os.path.join(DATA_DIR, safe_filename)
    
    with open(save_path, "wb") as f:
        f.write(await file.read())
        
    # 7日より大きい値（裏コマンド）が来たら永続化
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
    
    return {"url": f"/api/download/{uid}"}

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

# 管理用API
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

# UI（静的ファイル）の配信
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
