import os
import json
import logging
import re
import asyncio
import httpx
import socket
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── CONFIG ───────────────────────────────────────────────────────────────────
load_dotenv()


def env_value(name):
    value = os.getenv(name, "").strip()
    if not value or value.startswith("your_"):
        return ""
    return value


BOT_TOKEN = env_value("BOT_TOKEN")
OPENROUTER_API_KEY = env_value("OPENROUTER_API_KEY")
DATA_FILE = "reminders.json"
DEFAULT_TZ_KEY = os.getenv("DEFAULT_TZ", "seoul")
INSTANCE_LOCK_PORT = int(os.getenv("INSTANCE_LOCK_PORT", "47654"))
HEALTH_PORT = int(os.getenv("PORT", "0") or "0")
_INSTANCE_LOCK_SOCKET = None

TIMEZONES = {
    "tashkent": ZoneInfo("Asia/Tashkent"),
    "seoul":    ZoneInfo("Asia/Seoul"),
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def acquire_instance_lock():
    global _INSTANCE_LOCK_SOCKET

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", INSTANCE_LOCK_PORT))
        sock.listen(1)
    except OSError:
        logger.error(
            "Bot already running on this computer. Stop the old python bot.py process first."
        )
        sock.close()
        return False

    _INSTANCE_LOCK_SOCKET = sock
    return True


async def handle_health_check(reader, writer):
    await reader.read(1024)
    body = b"OK"
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 2\r\n"
        b"Connection: close\r\n"
        b"\r\n" + body
    )
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def start_health_server():
    if not HEALTH_PORT:
        return None

    server = await asyncio.start_server(handle_health_check, "0.0.0.0", HEALTH_PORT)
    logger.info(f"Health endpoint listening on port {HEALTH_PORT}")
    return server

# ─── STORAGE ──────────────────────────────────────────────────────────────────


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"reminders": [], "users": {}}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(cid):
    db = load_data()
    return db.get("users", {}).get(str(cid), {})


def set_user(cid, key, value):
    db = load_data()
    if "users" not in db:
        db["users"] = {}
    if str(cid) not in db["users"]:
        db["users"][str(cid)] = {}
    db["users"][str(cid)][key] = value
    save_data(db)


def get_lang(cid):
    return get_user(cid).get("lang", "uz")


def get_tz(cid):
    default_tz = DEFAULT_TZ_KEY if DEFAULT_TZ_KEY in TIMEZONES else "tashkent"
    tz_key = get_user(cid).get("tz", default_tz)
    return TIMEZONES.get(tz_key, TIMEZONES[default_tz])


def now_for(cid):
    return datetime.now(get_tz(cid))


# ─── TEXTS ────────────────────────────────────────────────────────────────────
TEXTS = {
    "choose_lang": {
        "uz": "Tilni tanlang / 언어를 선택하세요:",
        "ko": "Tilni tanlang / 언어를 선택하세요:",
    },
    "choose_tz": {
        "uz": "🌍 Vaqt zonasini tanlang:",
        "ko": "🌍 시간대를 선택하세요:",
    },
    "setup_done": {
        "uz": "✅ Sozlamalar saqlandi!\n\n👋 Salom! Men *하루지기* — kunning qo'riqchisiman.\n\nShunchaki menga yozing:\n💬 `Bugun soat 14:00da uchrashuv bor`\n💬 `Ertaga 9:00da shifokor`\n\nYoki buyruqlardan foydalaning:\n/list — Barcha eslatmalar\n/agenda — Bugungi reja\n/done — Bajarildi ✅\n/weekly — Haftalik takror 🔁\n/settings — Sozlamalar",
        "ko": "✅ 설정이 저장되었습니다!\n\n👋 안녕하세요! 저는 *하루지기* — 하루의 파수꾼입니다.\n\n그냥 말씀해 주세요:\n💬 `오늘 14시에 약속 있어`\n💬 `내일 오전 9시 병원 예약`\n\n또는 명령어 사용:\n/list — 모든 알림\n/agenda — 오늘 일정\n/done — 완료 표시 ✅\n/weekly — 매주 반복 🔁\n/settings — 설정",
    },
    "saved": {
        "uz": "✅ *Tasdiqlandi!*\n🕐 Vaqt: *{time}*\n📋 Ish: *{task}*\n⏰ 30 daqiqa avval eslatiladi",
        "ko": "✅ *확인되었습니다!*\n🕐 시간: *{time}*\n📋 일정: *{task}*\n⏰ 30분 전에 알림 드립니다",
    },
    "reminder_alert": {
        "uz": "⏰ *30 daqiqadan keyin:*\n📋 {task}\n🕐 {time}",
        "ko": "⏰ *30분 후:*\n📋 {task}\n🕐 {time}",
    },
    "reminder_now": {
        "uz": "🔔 *Hozir vaqt!*\n📋 {task}",
        "ko": "🔔 *지금 시간입니다!*\n📋 {task}",
    },
    "no_reminders": {
        "uz": "📭 Hozircha eslatma yo'q.",
        "ko": "📭 현재 알림이 없습니다.",
    },
    "agenda_header": {
        "uz": "📅 *Bugungi reja:*",
        "ko": "📅 *오늘의 일정:*",
    },
    "done_prompt": {
        "uz": "✅ Qaysi eslatmani bajarildi deb belgilash kerak?",
        "ko": "✅ 어떤 알림을 완료로 표시할까요?",
    },
    "marked_done": {
        "uz": "✅ Bajarildi: *{task}*",
        "ko": "✅ 완료: *{task}*",
    },
    "weekly_prompt": {
        "uz": "🔁 Haftalik eslatma:\n*Format:* `Dushanba 09:00 Xabar matni`\n\nKunlar: Dushanba, Seshanba, Chorshanba, Payshanba, Juma, Shanba, Yakshanba",
        "ko": "🔁 매주 반복 알림:\n*형식:* `월요일 09:00 내용`\n\n요일: 월요일, 화요일, 수요일, 목요일, 금요일, 토요일, 일요일",
    },
    "settings_info": {
        "uz": "⚙️ *Sizning sozlamalaringiz:*\n🌐 Til: {lang}\n🕐 Vaqt zonasi: {tz}\n\nO'zgartirish uchun /start ni bosing.",
        "ko": "⚙️ *현재 설정:*\n🌐 언어: {lang}\n🕐 시간대: {tz}\n\n변경하려면 /start 를 누르세요.",
    },
    "not_understood": {
        "uz": "🤔 Vaqtni aniqlay olmadim. Misol:\n`Bugun 14:00da uchrashuv` yoki `Ertaga soat 9da shifokor`",
        "ko": "🤔 시간을 파악하지 못했어요. 예시:\n`오늘 14시에 약속` 또는 `내일 오전 9시 병원`",
    },
    "weekly_saved": {
        "uz": "🔁 *Haftalik eslatma saqlandi!*\n📅 {day} {time}\n📋 {task}",
        "ko": "🔁 *매주 반복 알림이 저장되었습니다!*\n📅 {day} {time}\n📋 {task}",
    },
    "weekly_format_error": {
        "uz": "❌ Format noto'g'ri. Misol: `Dushanba 09:00 Yig'ilish`",
        "ko": "❌ 형식이 잘못되었습니다. 예: `월요일 09:00 회의`",
    },
}


def t(key, cid, **kwargs):
    lang = get_lang(cid)
    text = TEXTS[key].get(lang, TEXTS[key]["uz"])
    return text.format(**kwargs) if kwargs else text

# ─── AI: NATURAL LANGUAGE PARSER ──────────────────────────────────────────────


async def ai_parse_reminders(user_text: str, cid: int) -> list[dict] | None:
    """
    OpenRouter AI orqali xabardan ko'p vaqtlar va vazifalarni ajratib oladi.
    Qaytaradi: [{"date": "2026-06-02", "time": "14:00", "task": "Uchrashuv"}, ...] yoki None
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        return None
    
    now = now_for(cid)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    system_prompt = f"""You are a reminder time extractor. Current date and time: {now_str}.
Extract ALL reminders/schedules from the user message and return ONLY valid JSON array.

Rules:
- "오늘" or "bugun" = today ({now.strftime("%Y-%m-%d")})
- "내일" or "ertaga" = tomorrow ({(now + timedelta(days=1)).strftime("%Y-%m-%d")})
- "모레" or "indinga" = day after tomorrow
- For each reminder, parse: date and time (if given)
- "오전" = AM, "오후" = PM (add 12 if PM and hour < 12)
- "시" after number = hour (e.g. "3시" = 03:00, "오후 3시" = 15:00)
- If NO time mentioned for an item, use "00:00" (full day event)
- Month/Day format like "5/26" means May 26

Return JSON array format EXACTLY like this:
[
  {{"date": "YYYY-MM-DD", "time": "HH:MM", "task": "task description"}},
  {{"date": "YYYY-MM-DD", "time": "HH:MM", "task": "another task"}}
]

If message contains multiple items/schedules, extract ALL of them.
If you cannot parse any reminders, return:
[]

Return ONLY the JSON array, nothing else."""

    try:
        await asyncio.sleep(0.3)
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/reminder_bot",
            "X-Title": "Reminder Bot"
        }
        
        payload = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
        
        if resp.status_code == 429:
            logger.warning("OpenRouter API rate limited (429). Waiting...")
            await asyncio.sleep(1)
            return None
        
        if resp.status_code != 200:
            logger.error(f"OpenRouter API error: {resp.status_code} {resp.text}")
            return None
        
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            logger.error(f"OpenRouter parse error: No choices in response")
            return None
        
        raw = data["choices"][0]["message"]["content"].strip()
        import re as _re
        raw = _re.sub(r"^```json|^```|```$", "", raw,
                      flags=_re.MULTILINE).strip()
        parsed = json.loads(raw)
        
        if not isinstance(parsed, list):
            return None
        
        return parsed if parsed else None
    except Exception as e:
        logger.error(f"OpenRouter parse error: {e}")
        return None

# ─── PARSE HELPERS ────────────────────────────────────────────────────────────


def parse_reminder(text, cid):
    match = re.match(r"(\d{1,2}):(\d{2})\s+(.+)", text.strip())
    if not match:
        return None, None
    hour, minute, task = int(match.group(1)), int(
        match.group(2)), match.group(3)
    now = now_for(cid)
    remind_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if remind_dt <= now:
        remind_dt += timedelta(days=1)
    return remind_dt, task


WEEKDAY_MAP = {
    "dushanba": 0, "seshanba": 1, "chorshanba": 2,
    "payshanba": 3, "juma": 4, "shanba": 5, "yakshanba": 6,
    "월요일": 0, "화요일": 1, "수요일": 2,
    "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6,
}
DAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba",
           "Payshanba", "Juma", "Shanba", "Yakshanba"]
DAYS_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def parse_weekly(text):
    parts = text.strip().split()
    if len(parts) < 3:
        return None
    weekday = WEEKDAY_MAP.get(parts[0].lower())
    if weekday is None:
        return None
    tm = re.match(r"(\d{1,2}):(\d{2})", parts[1])
    if not tm:
        return None
    task = " ".join(parts[2:])
    return weekday, int(tm.group(1)), int(tm.group(2)), task


# ─── STATE ────────────────────────────────────────────────────────────────────
waiting_for = {}

# ─── HANDLERS ─────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"),
        InlineKeyboardButton("🇰🇷 한국어",  callback_data="lang_ko"),
    ]]
    await update.message.reply_text(
        "Tilni tanlang / 언어를 선택하세요:",
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat_id
    data = q.data

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        set_user(cid, "lang", lang)
        kb = [[
            InlineKeyboardButton("🕐 Toshkent (UTC+5)",
                                 callback_data="tz_tashkent"),
            InlineKeyboardButton("🕐 Seoul (UTC+9)",
                                 callback_data="tz_seoul"),
        ]]
        await q.edit_message_text(t("choose_tz", cid), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("tz_"):
        tz_key = data.split("_")[1]
        set_user(cid, "tz", tz_key)
        await q.edit_message_text(t("setup_done", cid), parse_mode="Markdown")

    elif data.startswith("done_"):
        idx = int(data.split("_")[1])
        db = load_data()
        user_reminders = [r for r in db["reminders"]
                          if r["chat_id"] == cid and not r.get("done")]
        if idx < len(user_reminders):
            target = user_reminders[idx]
            for r in db["reminders"]:
                if r["chat_id"] == cid and r["task"] == target["task"] and r["time"] == target["time"]:
                    r["done"] = True
                    break
            save_data(db)
            await q.edit_message_text(t("marked_done", cid, task=target["task"]), parse_mode="Markdown")


async def cmd_weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    waiting_for[cid] = "weekly"
    await update.message.reply_text(t("weekly_prompt", cid), parse_mode="Markdown")


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    db = load_data()
    now = now_for(cid)
    today = now.strftime("%Y-%m-%d")
    
    items = [r for r in db["reminders"]
             if r["chat_id"] == cid and not r.get("done")]
    
    # Geçmiş tarihli reminderleri filtrele (weekly hariç)
    items = [r for r in items 
             if r.get("weekly") or r["time"][:10] >= today]
    
    # Geçmiş tarihli reminderleri sil
    db["reminders"] = [r for r in db["reminders"]
                       if r.get("weekly") or r["time"][:10] >= today or r.get("done")]
    save_data(db)
    
    if not items:
        await update.message.reply_text(t("no_reminders", cid))
        return
    lines = []
    for r in sorted(items, key=lambda x: x["time"]):
        icon = "🔁" if r.get("weekly") else "🔔"
        if r.get("weekly"):
            parts = r["time"].split(":")
            time_str = f"{parts[2]}:{parts[3]}"
            lines.append(f"{icon} `{time_str}` — {r['task']}")
        else:
            date_str = r["time"][:10]
            time_str = r["time"][11:16]
            lines.append(f"{icon} `{date_str} {time_str}` — {r['task']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_agenda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    db = load_data()
    today = now_for(cid).strftime("%Y-%m-%d")
    items = [r for r in db["reminders"]
             if r["chat_id"] == cid and not r.get("done") and not r.get("weekly")
             and r["time"].startswith(today)]
    header = t("agenda_header", cid)
    if not items:
        await update.message.reply_text(header + "\n" + t("no_reminders", cid), parse_mode="Markdown")
        return
    lines = [header]
    for r in sorted(items, key=lambda x: x["time"]):
        lines.append(f"⏳ `{r['time'][11:16]}` — {r['task']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    db = load_data()
    items = [r for r in db["reminders"] if r["chat_id"] ==
             cid and not r.get("done") and not r.get("weekly")]
    if not items:
        await update.message.reply_text(t("no_reminders", cid))
        return
    kb = []
    for i, r in enumerate(items):
        kb.append([InlineKeyboardButton(
            f"🔔 {r['time'][11:16]} — {r['task']}", callback_data=f"done_{i}")])
    await update.message.reply_text(t("done_prompt", cid), reply_markup=InlineKeyboardMarkup(kb))


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    user = get_user(cid)
    lang_names = {"uz": "🇺🇿 O'zbek", "ko": "🇰🇷 한국어"}
    tz_names = {"tashkent": "🕐 Toshkent (UTC+5)", "seoul": "🕐 Seoul (UTC+9)"}
    await update.message.reply_text(
        t("settings_info", cid,
          lang=lang_names.get(user.get("lang", "uz"), "O'zbek"),
          tz=tz_names.get(user.get("tz", DEFAULT_TZ_KEY), "Seoul")),
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(t("setup_done", cid), parse_mode="Markdown")

# ─── MAIN MESSAGE HANDLER (natural language) ──────────────────────────────────


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    text = update.message.text or ""
    state = waiting_for.get(cid)

    # /weekly oqimi
    if state == "weekly":
        result = parse_weekly(text)
        if not result:
            await update.message.reply_text(t("weekly_format_error", cid), parse_mode="Markdown")
            return
        weekday, hour, minute, task = result
        db = load_data()
        db["reminders"].append({
            "chat_id": cid,
            "time": f"weekly:{weekday}:{hour:02d}:{minute:02d}",
            "task": task,
            "done": False,
            "weekly": True,
            "tz": get_user(cid).get("tz", DEFAULT_TZ_KEY),
        })
        save_data(db)
        waiting_for.pop(cid, None)
        day_name = DAYS_KO[weekday] if get_lang(
            cid) == "ko" else DAYS_UZ[weekday]
        await update.message.reply_text(
            t("weekly_saved", cid, day=day_name,
              time=f"{hour:02d}:{minute:02d}", task=task),
            parse_mode="Markdown"
        )
        return

    # Natural language — AI bilan tahlil qilish
    parsed_list = await ai_parse_reminders(text, cid)

    if parsed_list:
        try:
            db = load_data()
            tz = get_tz(cid)
            saved_count = 0
            
            for parsed in parsed_list:
                remind_dt = datetime.strptime(
                    f"{parsed['date']} {parsed['time']}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=tz)
                task = parsed["task"]

                reminder_dict = {
                    "chat_id": cid,
                    "time": remind_dt.strftime("%Y-%m-%d %H:%M"),
                    "task": task,
                    "done": False,
                    "weekly": False,
                    "tz": get_user(cid).get("tz", DEFAULT_TZ_KEY),
                }
                
                # Check duplicate - bu reminder avval saqlandi yo'qmi?
                is_duplicate = False
                for existing in db["reminders"]:
                    if (existing["chat_id"] == cid and 
                        existing["time"] == reminder_dict["time"] and 
                        existing["task"] == task and 
                        not existing.get("done")):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    db["reminders"].append(reminder_dict)
                    saved_count += 1
            
            save_data(db)
            
            if saved_count == 1:
                await update.message.reply_text(
                    t("saved", cid, time=parsed_list[0]['time'], task=parsed_list[0]["task"]),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"✅ *{saved_count}ta eslatma saqlandi!*\n(또는 {saved_count}개의 일정이 저장되었습니다)",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Save error: {e}")
            await update.message.reply_text(t("not_understood", cid))
    else:
        await update.message.reply_text(t("not_understood", cid))

# ─── SCHEDULER ────────────────────────────────────────────────────────────────


async def check_reminders(app):
    db = load_data()
    changed = False
    logger.info("🔔 Checking reminders...")

    for r in db["reminders"]:
        if r.get("done"):
            continue
        cid = r["chat_id"]
        tz_key = r.get("tz") or get_user(cid).get("tz", DEFAULT_TZ_KEY)
        tz = TIMEZONES.get(tz_key, TIMEZONES.get(DEFAULT_TZ_KEY, TIMEZONES["tashkent"]))
        now = datetime.now(tz)

        if not r.get("weekly"):
            try:
                remind_dt = datetime.strptime(
                    r["time"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            except Exception as e:
                logger.error(f"Reminder parse error: {r['time']} - {e}")
                continue
            diff = (remind_dt - now).total_seconds()
            alert_30_dt = remind_dt - timedelta(minutes=30)
            alert_30_diff = (now - alert_30_dt).total_seconds()
            
            logger.info(
                f"Task: {r['task']}, diff={int(diff)}s "
                f"(alert_30_diff={int(alert_30_diff)}s, "
                f"30min={0<=alert_30_diff<=90}, now={-60<=diff<=120})"
            )

            # 30-min alert: send at the alert time, with a short grace window for scheduler jitter.
            if 0 <= alert_30_diff <= 90 and not r.get("notified_30"):
                logger.info(f"✅ Sending 30-min alert for: {r['task']}")
                try:
                    await app.bot.send_message(
                        cid,
                        t("reminder_alert", cid,
                          task=r["task"], time=remind_dt.strftime("%H:%M")),
                        parse_mode="Markdown"
                    )
                    r["notified_30"] = True
                    changed = True
                except Exception as e:
                    logger.error(f"Failed to send 30-min alert: {e}")

            # At reminder time (-1 to +2 min window)
            if -60 <= diff <= 120 and not r.get("notified_now"):
                logger.info(f"✅ Sending now alert for: {r['task']}")
                try:
                    await app.bot.send_message(
                        cid,
                        t("reminder_now", cid, task=r["task"]),
                        parse_mode="Markdown"
                    )
                    r["notified_now"] = True
                    r["done"] = True
                    changed = True
                except Exception as e:
                    logger.error(f"Failed to send now alert: {e}")
        else:
            try:
                _, wd, h, m = r["time"].split(":")
                wd, h, m = int(wd), int(h), int(m)
            except Exception:
                continue
            if wd == now.weekday() and now.hour == h and now.minute == m:
                logger.info(f"✅ Sending weekly alert for: {r['task']}")
                try:
                    await app.bot.send_message(
                        cid,
                        t("reminder_now", cid, task=r["task"]),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send weekly alert: {e}")

    if changed:
        save_data(db)

# ─── MAIN ─────────────────────────────────────────────────────────────────────


async def post_init(app):
    logger.info("✅ App initialized")


async def main():
    health_server = await start_health_server()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("list",     cmd_list))
    app.add_handler(CommandHandler("agenda",   cmd_agenda))
    app.add_handler(CommandHandler("done",     cmd_done))
    app.add_handler(CommandHandler("weekly",   cmd_weekly))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    
    # Scheduler'ni start qil
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", seconds=30, args=[app], name="check_reminders")
    scheduler.start()
    logger.info("✅ Bot ishlamoqda... To'xtatish uchun Ctrl+C bosing.")
    logger.info("✅ Scheduler started - reminders checking every 30 seconds")
    
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown()
        if health_server:
            health_server.close()
            await health_server.wait_closed()
        await app.stop()

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Add it as an environment variable.")
        sys.exit(1)
    if not acquire_instance_lock():
        sys.exit(1)
    asyncio.run(main())
