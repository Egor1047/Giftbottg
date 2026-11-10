import asyncio, os, sqlite3, time, random
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.payments import GetUniqueStarGiftRequest
from telethon.tl.functions.users import GetUsersRequest
from telethon.errors import FloodWaitError

import db

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["SESSION_STRING"]
COLLECTIONS = [x.strip() for x in os.environ.get(
    "COLLECTIONS", "ChillFlame,PlushPepe,Heart").split(",") if x.strip()]
INTERVAL = int(os.environ.get("SCAN_INTERVAL", 3600))

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

async def scan(coll: str, upto: int = 5000):
    for n in range(1, upto + 1):
        slug = f"{coll}-{n}"
        with db.conn() as c:
            if c.execute("SELECT 1 FROM targets WHERE slug=?", (slug,)).fetchone():
                continue
        try:
            g = await client(GetUniqueStarGiftRequest(slug=slug))
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 2); continue
        except Exception:
            continue

        owner = getattr(g, "owner_id", None)
        if not owner:
            await asyncio.sleep(0.35); continue
        try:
            u = (await client(GetUsersRequest([owner])))[0]
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 2); continue
        except Exception:
            continue
        if not getattr(u, "username", None) or u.bot or u.deleted:
            await asyncio.sleep(0.35); continue

        with db.conn() as c:
            c.execute("INSERT OR IGNORE INTO targets(username,user_id,title,num,slug) "
                      "VALUES (?,?,?,?,?)", (u.username, u.id, getattr(g, "title", coll), n, slug))
        db.log(f"found @{u.username} {slug}")
        print("+", u.username, slug)
        await asyncio.sleep(0.35)

async def main():
    db.init()
    await client.start()
    while True:
        for coll in COLLECTIONS:
            try:
                await scan(coll)
            except Exception as e:
                db.log(f"scan {coll}: {e}")
        await asyncio.sleep(INTERVAL)

if __name__ == "__main__":
    client.loop.run_until_complete(main())
