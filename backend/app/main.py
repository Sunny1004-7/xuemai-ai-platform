from contextlib import asynccontextmanager
from pathlib import Path
import json
import secrets
import time
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .db import get_db, init_db
from .auth import current_user, verify_password


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app=FastAPI(title="学脉 XueMai API",version="0.6.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["Authorization","Content-Type"])
media=Path(__file__).resolve().parents[1]/"media"
media.mkdir(exist_ok=True)
app.mount("/media",StaticFiles(directory=media),name="media")


class Login(BaseModel):
    username:str=Field(min_length=1,max_length=80)
    password:str=Field(min_length=1,max_length=200)


@app.get("/api/health")
def health():
    from .ai import AIConfig
    return {"status":"ok","service":"学脉","synthetic_data":True,"ai_mode":AIConfig.from_env().mode}


@app.post("/api/auth/login")
def login(body:Login):
    with get_db() as db:
        user=db.execute("SELECT * FROM users WHERE username=? AND active=1",(body.username,)).fetchone()
        if not user or not verify_password(body.password,user["password_hash"]):
            raise HTTPException(401,"账号或密码不正确")
        token=secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires_at<?",(time.time(),))
        db.execute("INSERT INTO sessions VALUES(?,?,?)",(token,user["id"],time.time()+86400))
        return {"token":token,"user":{k:user[k] for k in ("id","username","name","role")}}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


@app.post("/api/auth/logout")
def logout(user=Depends(current_user)):
    # All sessions for this demo identity are revoked; refresh then requires sign in.
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
    return {"ok":True}


from .routes import router
app.include_router(router)
try:
    from .ai_routes import router as ai_router
except ModuleNotFoundError as exc:
    if exc.name not in {"backend.app.ai_routes","app.ai_routes"}:
        raise
else:
    app.include_router(ai_router)
from .ai_attachments import router as attachment_router
from .voice import router as voice_router
from .teacher_assistant import router as teacher_ai_router
app.include_router(attachment_router)
app.include_router(voice_router)
app.include_router(teacher_ai_router)
