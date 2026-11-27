import logging
import hashlib, hmac
from pathlib import Path
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, desc, func
from app.config import settings
from app.db import Session, Meme, Target
from app.core import MemeService

log = logging.getLogger(__name__)
service = MemeService()

def configure_service(core: MemeService):
    global service
    service = core

app = FastAPI(title="Memovoz Admin")
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=settings.cookie_https_only)
base = Path(__file__).parent
app.mount("/static", StaticFiles(directory=base / "static"), name="static")
templates = Jinja2Templates(directory=str(base / "templates"))

async def auth(request: Request):
    if not request.session.get("logged_in"): raise HTTPException(status_code=401, detail="Sign in at /login")

@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=303)
    return await http_exception_handler(request, exc)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error":""})

@app.post("/login")
async def login(request: Request, username: str=Form(...), password: str=Form(...)):
    valid = False
    encoded = settings.admin_password_hash.split("$")
    if len(encoded) == 3 and encoded[0] == "scrypt":
        try:
            actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(encoded[1]), n=16384, r=8, p=1).hex()
            valid = hmac.compare_digest(actual, encoded[2])
        except (ValueError, TypeError):
            valid = False
    if username == settings.admin_username and valid:
        request.session.clear()
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error":"Неверный логин или пароль"}, status_code=401)

@app.post("/logout")
async def logout(request: Request):
    request.session.clear(); return RedirectResponse("/login", status_code=303)

def _logs():
    try: return Path("data/memovoz.log").read_text(encoding="utf-8").splitlines()[-200:]
    except OSError: return ["Лог-файл появится после первой записи."]

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(auth)])
async def dashboard(request: Request, q: str="", status: str="", page: int=1):
    page = max(1, page)
    async with Session() as s:
        filters = []
        if status: filters.append(Meme.status == status)
        if q: filters.append(Meme.title.ilike(f"%{q}%"))
        total = await s.scalar(select(func.count()).select_from(Meme).where(*filters)) or 0
        memes = list((await s.scalars(select(Meme).where(*filters).order_by(desc(Meme.added_at)).limit(100).offset((page - 1) * 100))).all())
        targets = list((await s.scalars(select(Target).order_by(Target.platform))).all())
    stats = await service.stats()
    return templates.TemplateResponse(request=request, name="index.html", context={"memes":memes,"targets":targets,"stats":stats,"q":q,"status":status,"page":page,"has_prev":page>1,"has_next":page*100<total,"total_filtered":total,"logs":_logs(),"post_interval":await service.get_setting("post_interval_minutes",str(settings.post_interval_minutes)),"poll_interval":await service.get_setting("poll_interval_minutes",str(settings.poll_interval_minutes)),"new_pin_mode":await service.get_setting("new_pin_mode",settings.new_pin_mode)})

async def _pin_for_id(meme_id):
    async with Session() as s:
        item=await s.get(Meme,meme_id); return item.pin_id if item else ""

@app.post("/meme/{meme_id}/send", dependencies=[Depends(auth)])
async def send_now(meme_id:int):
    await service.post_by_pin(await _pin_for_id(meme_id)); return RedirectResponse("/",303)

@app.post("/meme/{meme_id}/skip", dependencies=[Depends(auth)])
async def skip(meme_id:int): await service.mark(meme_id,"skipped"); return RedirectResponse("/",303)

@app.post("/meme/{meme_id}/queue", dependencies=[Depends(auth)])
async def queue(meme_id:int): await service.mark(meme_id,"queued"); return RedirectResponse("/",303)

@app.post("/meme/{meme_id}/delete", dependencies=[Depends(auth)])
async def delete(meme_id:int): await service.delete(meme_id); return RedirectResponse("/",303)

@app.post("/settings", dependencies=[Depends(auth)])
async def save_settings(post_interval:int=Form(...), poll_interval:int=Form(...), new_pin_mode:str=Form(...), paused: str=""):
    if new_pin_mode not in {"immediate", "queue"}: raise HTTPException(400, "Invalid new pin mode")
    await service.set_setting("post_interval_minutes", max(1,post_interval)); await service.set_setting("poll_interval_minutes", max(1,poll_interval))
    await service.set_setting("new_pin_mode",new_pin_mode); await service.set_setting("paused",str(paused == "on").lower())
    return RedirectResponse("/",303)

@app.post("/targets", dependencies=[Depends(auth)])
async def add_target(platform:str=Form(...),target_id:str=Form(...),label:str=Form("")):
    if platform not in {"telegram","discord"}: raise HTTPException(400,"Unknown platform")
    target_id = target_id.strip()
    if not target_id: raise HTTPException(400, "Target ID is required")
    async with Session() as s:
        exists=await s.scalar(select(Target).where(Target.platform==platform,Target.target_id==target_id))
        if not exists: s.add(Target(platform=platform,target_id=target_id,label=label or target_id)); await s.commit()
    return RedirectResponse("/",303)

@app.post("/targets/{target_id}/delete", dependencies=[Depends(auth)])
async def remove_target(target_id:int):
    async with Session() as s:
        item=await s.get(Target,target_id)
        if item: await s.delete(item); await s.commit()
    return RedirectResponse("/",303)
