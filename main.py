import httpx
import json
import base64
import time
import os
import sys
import random
import re
import asyncio
from datetime import datetime
from ex.colors import colors
from ex.intro import intro

# Configuration
API_BASE = "https://discord.com/api/v9"
POLL_INTERVAL = 40
HEARTBEAT_INTERVAL = 20
LOG_PROGRESS = True

SUPPORTED_TASKS = [
    "WATCH_VIDEO",
    "PLAY_ON_DESKTOP",
    "STREAM_ON_DESKTOP",
    "PLAY_ACTIVITY",
    "WATCH_VIDEO_ON_MOBILE"
]

# Shared state for UI
active_tasks = {}  # { (token_hint, qid): status_text }
session_completed = 0
ui_lock = asyncio.Lock()

def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefixes = {
        "info": f"{colors.qkhanhz_sys[0]}System{colors.reset}",
        "ok": f"{colors.qkhanhz_ok[0]}Online{colors.reset}",
        "warn": f"{colors.qkhanhz_coder[0]}Notice{colors.reset}",
        "error": f"{colors.qkhanhz_err[0]}Faulty{colors.reset}",
        "progress": f"{colors.dim}Action{colors.reset}",
        "debug": f"{colors.dim}Report{colors.reset}"
    }
    prefix = prefixes.get(level, level.upper()).ljust(8)
    
    if LOG_PROGRESS or level != "progress":
        print(f"{colors.dim}{ts}{colors.reset}  {prefix}  {msg}")

async def fetch_latest_build_number():
    fallback = 504649
    try:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get("https://discord.com/app", headers={"User-Agent": ua})
            if res.status_code != 200:
                return fallback
            
            text = res.text
            env_match = re.search(r'GLOBAL_ENV\s*=\s*({.*?});', text)
            if env_match:
                try:
                    env = json.loads(env_match.group(1))
                    if "buildNumber" in env:
                        return int(env["buildNumber"])
                except: pass
            
            scripts = re.findall(r'src="/assets/([^"]+\.js)"', text)
            if not scripts: return fallback
            
            for asset_path in reversed(scripts[-5:]):
                try:
                    asset_url = asset_path if asset_path.startswith("http") else f"https://discord.com/assets/{asset_path.replace('/assets/', '')}"
                    asset_res = await client.get(asset_url, headers={"User-Agent": ua})
                    m = re.search(r'buildNumber["\s:]+["\s]*(\d{5,7})', asset_res.text)
                    if m: return int(m.group(1))
                except: pass
            return fallback
    except:
        return fallback

def make_super_properties(build_number):
    obj = {
        "os": "Windows", "browser": "Discord Client", "release_channel": "stable",
        "client_version": "1.0.9175", "os_version": "10.0.26100", "os_arch": "x64",
        "app_arch": "x64", "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9175 Chrome/128.0.6613.186 Electron/32.2.7 Safari/537.36",
        "browser_version": "32.2.7", "client_build_number": build_number,
        "native_build_number": 59498, "client_event_source": None
    }
    return base64.b64encode(json.dumps(obj).encode()).decode()

class DiscordApi:
    def __init__(self, token, build_number):
        self.token = token
        self.username = "Unknown"
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9175 Chrome/128.0.6613.186 Electron/32.2.7 Safari/537.36"
        sp = make_super_properties(build_number)
        self.headers = {
            "Authorization": token, "Content-Type": "application/json",
            "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9", "User-Agent": ua,
            "X-Super-Properties": sp, "X-Discord-Locale": "en-US",
            "X-Discord-Timezone": "Asia/Ho_Chi_Minh", "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=20, follow_redirects=True)

    async def get(self, path):
        return await self.client.get(f"{API_BASE}{path}")

    async def post(self, path, payload=None):
        return await self.client.post(f"{API_BASE}{path}", json=payload)

    async def validate_token(self):
        try:
            res = await self.get("/users/@me")
            if res.status_code == 200:
                user = res.json()
                self.username = user.get('username', 'Unknown')
                log(f"Đăng nhập: {colors.bold}{self.username}{colors.reset}", "ok")
                return True
            return False
        except: return False

    async def close(self):
        await self.client.aclose()

def get_val(d, *keys):
    if not d: return None
    for k in keys:
        if k in d: return d[k]
    return None

def get_task_config(quest):
    cfg = quest.get("config", {})
    return get_val(cfg, "taskConfig", "task_config", "taskConfigV2", "task_config_v2")

def get_quest_name(quest):
    cfg = quest.get("config", {})
    msgs = cfg.get("messages", {})
    name = get_val(msgs, "questName", "quest_name") or get_val(msgs, "gameTitle", "game_title")
    if name: return name.strip()
    return cfg.get("application", {}).get("name") or f"Quest#{quest.get('id')}"

def get_expires_at(quest):
    return get_val(quest.get("config", {}), "expiresAt", "expires_at")

def get_user_status(quest):
    us = get_val(quest, "userStatus", "user_status")
    return us if isinstance(us, dict) else {}

def is_completable(quest):
    expires = get_expires_at(quest)
    if expires:
        try:
            if datetime.fromisoformat(expires.replace("Z", "+00:00")).timestamp() <= time.time(): return False
        except: pass
    tc = get_task_config(quest)
    if not tc or "tasks" not in tc: return False
    return any(t in tc["tasks"] for t in SUPPORTED_TASKS)

def is_enrolled(quest):
    return bool(get_val(get_user_status(quest), "enrolledAt", "enrolled_at"))

def is_completed(quest):
    return bool(get_val(get_user_status(quest), "completedAt", "completed_at"))

def get_task_type(quest):
    tc = get_task_config(quest)
    if not tc or "tasks" not in tc: return None
    for t in SUPPORTED_TASKS:
        if t in tc["tasks"]: return t
    return None

def get_seconds_needed(quest):
    tc = get_task_config(quest)
    tt = get_task_type(quest)
    return tc["tasks"][tt].get("target", 0) if tc and tt else 0

def get_seconds_done(quest):
    tt = get_task_type(quest)
    if not tt: return 0
    return get_user_status(quest).get("progress", {}).get(tt, {}).get("value", 0)

def draw_progress_bar(current, total, width=15):
    percent = min(100, max(0, (current / total) * 100)) if total > 0 else 0
    filled = int((percent / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {percent:4.1f}%"

async def update_task_ui(key, msg):
    async with ui_lock:
        active_tasks[key] = msg

class QuestAutocompleter:
    def __init__(self, api, settings):
        self.api = api
        self.settings = settings
        self.completed_ids = set()
        self.token_hint = api.username

    async def fetch_quests(self):
        try:
            res = await self.api.get("/quests/@me")
            if res.status_code == 200:
                data = res.json()
                return data.get("quests", []) if isinstance(data, dict) else data
            elif res.status_code == 429:
                await asyncio.sleep(res.json().get("retry_after", 5))
                return await self.fetch_quests()
            return []
        except: return []

    async def enroll_quest(self, quest):
        qid = quest["id"]
        name = get_quest_name(quest)
        res = await self.api.post(f"/quests/{qid}/enroll", {
            "location": 11, "is_targeted": False,
            "traffic_metadata_raw": quest.get("traffic_metadata_raw"),
            "traffic_metadata_sealed": quest.get("traffic_metadata_sealed")
        })
        if res.status_code in [200, 201, 204]:
            log(f"[{self.token_hint}] Đã nhận: {colors.bold}{name}{colors.reset}", "ok")
            return True
        return False

    async def complete_video(self, quest):
        global session_completed
        qid, name = quest["id"], get_quest_name(quest)
        sec_needed = get_seconds_needed(quest)
        sec_done = get_seconds_done(quest)
        
        flow_colors = ["\x1b[35m", "\x1b[32m", "\x1b[36m", "\x1b[33m", "\x1b[37m"]
        idx = 0
        key = (self.token_hint, qid)
        
        while sec_done < sec_needed:
            timestamp = sec_done + 7
            try:
                res = await self.api.post(f"/quests/{qid}/video-progress", {"timestamp": min(sec_needed, timestamp + random.random())})
                if res.status_code == 200:
                    if res.json().get("completed_at"): break
                    sec_done = min(sec_needed, timestamp)
                elif res.status_code == 429:
                    await asyncio.sleep(res.json().get("retry_after", 5) + 1)
                    continue
            except: pass

            for _ in range(140): # ~7 seconds
                if sec_done >= sec_needed: break
                sub = min(sec_needed, sec_done + (_ / 140) * 7)
                bar = draw_progress_bar(sub, sec_needed)
                c = flow_colors[idx % 5]
                await update_task_ui(key, f"[{self.token_hint}] {c}Running{colors.reset}  [{name[:15].ljust(15)}] {bar} {int(sub):3}/{sec_needed}s")
                idx += 1
                await asyncio.sleep(0.05)
        
        await self.api.post(f"/quests/{qid}/video-progress", {"timestamp": sec_needed})
        async with ui_lock:
            session_completed += 1
            active_tasks.pop(key, None)
        log(f"[{self.token_hint}] Xong Video: {colors.bold}{name}{colors.reset}", "ok")

    async def complete_heartbeat(self, quest, is_activity=False):
        global session_completed
        qid, name = quest["id"], get_quest_name(quest)
        tt = get_task_type(quest)
        sec_needed = get_seconds_needed(quest)
        sec_done = get_seconds_done(quest)
        pid = random.randint(1000, 30000)
        
        flow_colors = ["\x1b[35m", "\x1b[32m", "\x1b[36m", "\x1b[33m", "\x1b[37m"]
        idx = 0
        key = (self.token_hint, qid)

        while sec_done < sec_needed:
            try:
                res = await self.api.post(f"/quests/{qid}/heartbeat", {"stream_key": f"call:0:{pid}" if not is_activity else "call:0:1", "terminal": False})
                if res.status_code == 200:
                    body = res.json()
                    prog = body.get("progress", {})
                    if tt in prog: sec_done = prog[tt].get("value", sec_done)
                    if body.get("completed_at") or sec_done >= sec_needed: break
                elif res.status_code == 429:
                    await asyncio.sleep(res.json().get("retry_after", 10) + 1)
                    continue
            except: pass

            for _ in range(400): # ~20 seconds
                if sec_done >= sec_needed: break
                sub = min(sec_needed, sec_done + (_ / 400) * HEARTBEAT_INTERVAL)
                bar = draw_progress_bar(sub, sec_needed)
                c = flow_colors[idx % 5]
                await update_task_ui(key, f"[{self.token_hint}] {c}Running{colors.reset}  [{name[:15].ljust(15)}] {bar} {int(sub):3}/{sec_needed}s")
                idx += 1
                await asyncio.sleep(0.05)

        await self.api.post(f"/quests/{qid}/heartbeat", {"stream_key": f"call:0:{pid}" if not is_activity else "call:0:1", "terminal": True})
        async with ui_lock:
            session_completed += 1
            active_tasks.pop(key, None)
        log(f"[{self.token_hint}] Xong Quest: {colors.bold}{name}{colors.reset}", "ok")

    async def process_quest(self, quest):
        qid, tt = quest["id"], get_task_type(quest)
        if not tt or qid in self.completed_ids: return
        self.completed_ids.add(qid)
        if tt in ["WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"]:
            await self.complete_video(quest)
        elif tt in ["PLAY_ON_DESKTOP", "STREAM_ON_DESKTOP"]:
            await self.complete_heartbeat(quest)
        elif tt == "PLAY_ACTIVITY":
            await self.complete_heartbeat(quest, True)

    async def run_forever(self):
        while True:
            quests = await self.fetch_quests()
            if quests:
                actionable = [q for q in quests if is_completable(q) and not is_completed(q)]
                for q in actionable:
                    if not is_enrolled(q) and self.settings.get("auto_accept", True):
                        await self.enroll_quest(q)
                
                to_process = [q for q in actionable if is_enrolled(q) and q["id"] not in self.completed_ids]
                for q in to_process:
                    asyncio.create_task(self.process_quest(q))

            await asyncio.sleep(self.settings.get("poll_interval", 40))

async def ui_runner(start_time):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        runtime = int(time.time() - start_time)
        c = colors.qkhanhzdz
        print(f"{c[0]}Quests {c[1]}Fast {c[2]}Multi {c[3]}By QKhanhZ{colors.reset} — {colors.dim}Phiên: {runtime//60}m {runtime%60}s | Xong: {session_completed}{colors.reset}")
        print(f"{colors.dim}{'─' * 80}{colors.reset}")
        
        async with ui_lock:
            if active_tasks:
                print(f"  {colors.bold}Active Tasks:{colors.reset}")
                for msg in active_tasks.values():
                    print(f"  {msg}")
            else:
                print(f"  {colors.dim}No active tasks. Waiting for new quests...{colors.reset}")
        
        print(f"\n{colors.dim}Đang cập nhật...{colors.reset}", end="", flush=True)
        await asyncio.sleep(0.5)

async def start_account(token, build_num, settings):
    api = DiscordApi(token, build_num)
    if await api.validate_token():
        bot = QuestAutocompleter(api, settings)
        await bot.run_forever()
    else:
        log(f"Token không hợp lệ: {token[:10]}...", "error")
    await api.close()

async def amain():
    intro()
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    
    tokens = config.get("tokens", [])
    settings = config.get("settings", {})
    
    if not tokens:
        log("Không tìm thấy token trong config.json", "error")
        return

    build_num = await fetch_latest_build_number()
    start_time = time.time()
    
    # Start UI in background
    asyncio.create_task(ui_runner(start_time))
    
    # Start all accounts
    tasks = [start_account(t, build_num, settings) for t in tokens]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Lỗi: {e}")
