"""Referal kredit va reyting mantig'i uchun minimal tekshiruv: `python test_db.py`."""
import asyncio
import os
import tempfile

import db


async def run():
    db.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
    await db.init_db()

    # 1) inviter ro'yxatdan o'tadi (taklifsiz)
    await db.start_user(1, None)
    await db.set_name(1, "Inviter")
    assert await db.complete_registration(1, "+998900000001") is None

    # 2) invitee 1-user havolasi orqali keladi -> kredit 1-userga tushadi
    await db.start_user(2, 1)
    await db.set_name(2, "Invitee")
    assert await db.complete_registration(2, "+998900000002") == 1
    assert await db.get_coins(1) == 1

    # 3) takroriy yakunlash — qo'shimcha coin YO'Q
    assert await db.complete_registration(2, "+998900000002") is None
    assert await db.get_coins(1) == 1

    # 4) o'zini o'zi taklif qilish e'tiborsiz
    await db.start_user(3, 3)
    assert (await db.get_user(3))["inviter_id"] is None

    # 5) reyting: 1-user (1 coin) -> #1, 2-user (0 coin) -> #2
    assert (await db.get_rank(1))[0] == 1
    assert (await db.get_rank(2))[0] == 2

    print("OK")


if __name__ == "__main__":
    asyncio.run(run())
