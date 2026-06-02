# 🤖 Reminder Bot — O'zbek & 한국어

## Ishga tushirish (3 qadam)

## Bot token olish

Linux/VPS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

```text
BOT_TOKEN=telegram_bot_tokeningiz
OPENROUTER_API_KEY=openrouter_api_keyingiz
DEFAULT_TZ=seoul
```

## O'rnatish va ishga tushirish

```bash
pip install -r requirements.txt
python bot.py
```


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
