import os
import time
from typing import List, Optional

import aiosqlite

from .config import App


class Database:
    def __init__(self, db_path: str = ''):
        self._db_path = db_path or os.environ.get('DB_PATH', App.DB_PATH)

    @property
    def db_path(self):
        return self._db_path

    @db_path.setter
    def db_path(self, value):
        if value:
            self._db_path = value

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    size       TEXT NOT NULL DEFAULT 'medium',
                    language   TEXT NOT NULL DEFAULT 'en',
                    created_at INTEGER NOT NULL
                )
            ''')
            await self._migrate(db)
            await db.commit()

    async def _migrate(self, db: aiosqlite.Connection):
        cursor = await db.execute('PRAGMA table_info(users)')
        columns = {row[1] for row in await cursor.fetchall()}
        if 'voice' not in columns:
            await db.execute('ALTER TABLE users ADD COLUMN voice TEXT')

    async def ensure_user(self, user_id: int, size: str = 'medium', language: str = 'en') -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if await cursor.fetchone() is None:
                await db.execute(
                    'INSERT INTO users (user_id, size, language, created_at) VALUES (?, ?, ?, ?)',
                    (user_id, size, language, int(time.time()))
                )
                await db.commit()
                return True
            return False

    async def is_authorized(self, user_id: int) -> bool:
        return await self.get_settings(user_id) is not None

    async def get_settings(self, user_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT user_id, size, language, voice, created_at FROM users WHERE user_id = ?',
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'size': row[1],
                    'language': row[2],
                    'voice': row[3],
                    'created_at': row[4],
                }
            return None

    async def set_size(self, user_id: int, size: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET size = ? WHERE user_id = ?', (size, user_id))
            await db.commit()

    async def set_language(self, user_id: int, language: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
            await db.commit()

    async def set_voice(self, user_id: int, voice: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE users SET voice = ? WHERE user_id = ?', (voice, user_id))
            await db.commit()

    async def fetch_all_user_ids(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT user_id FROM users')
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def count_users(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM users')
            row = await cursor.fetchone()
            return row[0] if row else 0


db = Database('')
