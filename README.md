# 🤖 Reminder Bot — O'zbek & 한국어

## Ishga tushirish (3 qadam)

### 1. Bot token olish

1. Telegramda [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini kiriting (misol: `MyReminderBot`)
4. Tokenni nusxalang (misol: `7123456789:AAHxxx...`)

### 2. Token va API keylarni `.env` faylga qo'yish

Maxfiy tokenlarni `bot.py` ichiga yozmang. `.env.example` faylidan nusxa olib `.env` yarating.

Linux/VPS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`.env` ichini to'ldiring:

```text
BOT_TOKEN=telegram_bot_tokeningiz
OPENROUTER_API_KEY=openrouter_api_keyingiz
DEFAULT_TZ=seoul
```

`.env` fayl GitHubga yuklanmasligi kerak. U `.gitignore` ichiga qo'shilgan.

### 3. O'rnatish va ishga tushirish

```bash
pip install -r requirements.txt
python bot.py
```

---

## ☁️ 24/7 ishlashi uchun (bepul)

### Railway (tavsiya etiladi)

1. [railway.app](https://railway.app) da ro'yxatdan o'ting
2. "New Project" → "Deploy from GitHub"
3. Bu papkani GitHub ga yuklang
4. Environment variable: `BOT_TOKEN = sizning_tokeningiz`
5. Deploy tugmasini bosing ✅

### Render

1. [render.com](https://render.com) da ro'yxatdan o'ting
2. New → Background Worker
3. Build: `pip install -r requirements.txt`
4. Start: `python bot.py`
5. Env var: `BOT_TOKEN`

---

## Buyruqlar

| Buyruq    | O'zbek                 | 한국어           |
| --------- | ---------------------- | ---------------- |
| `/start`  | Boshlash + til tanlash | 시작 + 언어 선택 |
| `/remind` | Eslatma qo'shish       | 알림 추가        |
| `/list`   | Barcha eslatmalar      | 모든 알림        |
| `/agenda` | Bugungi reja           | 오늘 일정        |
| `/done`   | Bajarildi belgisi      | 완료 표시        |
| `/weekly` | Haftalik eslatma       | 매주 반복        |

## Format

**Oddiy eslatma:**

```
/remind
→ 14:30 Shifokor bilan uchrashuv
```

**Haftalik:**

```
/weekly
→ Dushanba 09:00 Haftalik yig'ilish
```

---

## Vaqt zonasi

`bot.py` da `TIMEZONE` ni o'zgartiring:

- O'zbekiston: `Asia/Tashkent`
- Koreya: `Asia/Seoul`
- Moskva: `Europe/Moscow`

---

## 24/7 bepul ishlatish: Render + UptimeRobot

Oracle Cloudga registratsiya bo'lmasa, eng amaliy bepul variant:
Render Free Web Service + UptimeRobot ping.

Render Free Web Service 15 daqiqa traffic bo'lmasa uxlaydi. UptimeRobot free monitor esa har 5 daqiqada `/health` endpointga so'rov yuboradi va service uyg'oq turadi.

### 1. GitHubga yuklash

1. GitHubda yangi repository oching.
2. Shu loyiha fayllarini repositoryga push qiling.
3. `reminders.json` ichida test yoki shaxsiy ma'lumotlar bo'lsa, avval tozalab qo'ying.

### 2. Renderda Web Service yaratish

1. https://render.com saytida account oching.
2. Dashboard -> New -> Web Service ni tanlang.
3. GitHub repositoryni ulang.
4. Sozlamalarni shunday kiriting:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: python bot.py
Instance Type: Free
```

### 3. Environment Variables

Render service ichida Environment bo'limiga kiring va qo'shing:

```text
BOT_TOKEN=telegram_bot_tokeningiz
OPENROUTER_API_KEY=openrouter_api_keyingiz
DEFAULT_TZ=seoul
```

`PORT` ni qo'lda qo'shmang. Render o'zi beradi.

### 4. Deploy

Create Web Service / Deploy tugmasini bosing. Logs bo'limida shunga o'xshash yozuvlar chiqishi kerak:

```text
Health endpoint listening on port ...
Bot ishlamoqda...
Scheduler started
```

### 5. UptimeRobot sozlash

1. https://uptimerobot.com saytida account oching.
2. New Monitor bosing.
3. Monitor Type: HTTP(s)
4. URL:

```text
https://SIZNING-RENDER-URL.onrender.com/health
```

5. Monitoring Interval: 5 minutes
6. Create Monitor bosing.

### Muhim cheklovlar

- Kompyuteringizda `python bot.py` ni ishga tushirmang. Aks holda Telegram `409 Conflict` beradi.
- Render Free filesystem vaqtinchalik. Redeploy yoki restart bo'lsa `reminders.json`dagi yangi ma'lumotlar yo'qolishi mumkin.
- Ishonchli production uchun keyingi qadam: `reminders.json` o'rniga database ishlatish.
- Railway hozir to'liq bepul 24/7 emas; ko'proq trial yoki pullik Hobby planga yaqin.
- Render Background Worker free emas, shuning uchun Web Service + `/health` usulidan foydalanamiz.

---

## Hostinger VPS orqali 24/7 deploy

Hostinger VPS mavjud bo'lsa, eng yaxshi variant shu. Bot `systemd` service sifatida ishlaydi va server restart bo'lsa ham avtomatik qayta ochiladi.

### 1. VPS serverga kirish

Hostinger hPanel -> VPS -> Manage bo'limidan server IP manzilini oling. Terminalda:

```bash
ssh root@SERVER_IP
```

Agar SSH key ishlatsangiz:

```bash
ssh -i /path/to/key root@SERVER_IP
```

### 2. Kerakli paketlarni o'rnatish

Ubuntu/Debian VPS uchun:

```bash
apt update
apt install -y python3 python3-pip python3-venv git
```

### 3. Loyihani serverga yuklash

Eng oson yo'l: GitHub orqali.

```bash
cd /opt
git clone YOUR_GITHUB_REPO_URL reminder_bot
cd /opt/reminder_bot
```

Agar GitHub ishlatmasangiz, fayllarni hPanel File Manager yoki `scp` orqali `/opt/reminder_bot` papkasiga yuklang.

### 4. Python virtual environment

```bash
cd /opt/reminder_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Botni test qilish

Tokenlarni vaqtincha terminalda kiriting:

```bash
export BOT_TOKEN="telegram_bot_tokeningiz"
export OPENROUTER_API_KEY="openrouter_api_keyingiz"
export DEFAULT_TZ="seoul"
python bot.py
```

Telegramda botga xabar yuborib tekshiring. Ishlasa `Ctrl+C` bilan to'xtating.

### 6. systemd service yaratish

```bash
nano /etc/systemd/system/reminder-bot.service
```

Ichiga shuni yozing:

```ini
[Unit]
Description=Telegram Reminder Bot
After=network.target

[Service]
WorkingDirectory=/opt/reminder_bot
ExecStart=/opt/reminder_bot/.venv/bin/python bot.py
Restart=always
RestartSec=5
Environment=BOT_TOKEN=telegram_bot_tokeningiz
Environment=OPENROUTER_API_KEY=openrouter_api_keyingiz
Environment=DEFAULT_TZ=seoul

[Install]
WantedBy=multi-user.target
```

Saqlash:

- `Ctrl+O`
- `Enter`
- `Ctrl+X`

### 7. Service ishga tushirish

```bash
systemctl daemon-reload
systemctl enable reminder-bot
systemctl start reminder-bot
```

Status ko'rish:

```bash
systemctl status reminder-bot
```

Live log:

```bash
journalctl -u reminder-bot -f
```

Restart:

```bash
systemctl restart reminder-bot
```

To'xtatish:

```bash
systemctl stop reminder-bot
```

### 8. Yangilash

Kod o'zgarsa:

```bash
cd /opt/reminder_bot
git pull
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart reminder-bot
```

### Muhim

- VPSda bot ishlayotgan paytda lokal kompyuterda `python bot.py` qilmang. Aks holda Telegram `409 Conflict` beradi.
- `BOT_TOKEN`ni kod ichiga yozmang. Faqat `systemd` Environment orqali bering.
- `reminders.json` `/opt/reminder_bot` ichida saqlanadi. Backup qilish tavsiya etiladi.
