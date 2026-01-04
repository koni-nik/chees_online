"""
Скрипт миграции данных к версии 2.8.
Создаёт guest аккаунты для всех существующих player_id.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db
from auth import auth_manager
from logger import setup_logger

logger = setup_logger()


async def migrate_existing_players():
    """
    Мигрирует существующих игроков, создавая для них guest аккаунты.
    """
    logger.info("Начало миграции к версии 2.8...")
    
    try:
        # Инициализируем БД (создадим новые таблицы если их нет)
        await db.initialize()
        
        # Получаем всех существующих игроков из таблицы players
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT player_id FROM players WHERE user_id IS NULL")
            rows = await cursor.fetchall()
            existing_players = [row[0] for row in rows]
        
        if not existing_players:
            logger.info("Нет игроков для миграции")
            return
        
        logger.info(f"Найдено {len(existing_players)} игроков для миграции")
        
        migrated_count = 0
        
        for player_id in existing_players:
            try:
                # Создаём guest пользователя
                username = f"guest_{player_id}"
                email = f"guest_{player_id}@temp.local"
                password = "migrated_account_no_password"  # Пароль не используется для guest аккаунтов
                
                # Проверяем, не существует ли уже пользователь
                existing_user = await db.get_user_by_email(email)
                if existing_user:
                    # Пользователь уже существует, просто связываем
                    user_id = existing_user["id"]
                else:
                    # Создаём нового guest пользователя (is_guest передаётся как параметр, но его нет в текущей схеме)
                    # Пока просто создаём обычного пользователя, guest помечается через username/email
                    password_hash = auth_manager.hash_password(password)
                    user_id = await db.create_user(username, email, password_hash)
                    logger.debug(f"Создан guest пользователь для player_id {player_id}: user_id={user_id}")
                
                # Связываем player_id с user_id (обновляем таблицу players)
                import aiosqlite
                async with aiosqlite.connect(db.db_path) as conn:
                    await conn.execute(
                        "UPDATE players SET user_id = ? WHERE player_id = ?",
                        (user_id, player_id)
                    )
                    await conn.commit()
                
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    logger.info(f"Мигрировано {migrated_count}/{len(existing_players)} игроков...")
                    
            except Exception as e:
                logger.error(f"Ошибка миграции игрока {player_id}: {e}", exc_info=True)
                continue
        
        logger.info(f"Миграция завершена. Успешно мигрировано {migrated_count}/{len(existing_players)} игроков")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}", exc_info=True)
        raise


async def main():
    """Главная функция для запуска миграции."""
    try:
        await migrate_existing_players()
        print("Миграция успешно завершена!")
    except Exception as e:
        print(f"Ошибка миграции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

