"""Робота з базою даних SQLite.

Тут зібрано все спільне: підключення, ініціалізацію таблиць і допоміжні функції.
Файли з маршрутами (routes/*.py) імпортують звідси get_db, query_db та execute_db.
"""
import sqlite3

from flask import current_app, g

# Статуси замовлень: ключ зберігається в БД, значення показується користувачу.
ORDER_STATUSES = {
    'new': 'Нове',
    'preparing': 'Готується',
    'delivering': 'Доставляється',
    'done': 'Виконано',
    'cancelled': 'Скасовано',
}

# Тестові товари: додаються лише тоді, коли таблиця products порожня.
SEED_PRODUCTS = [
    ('Еспресо', 'Класичний міцний еспресо.', 45, 'Кава'),
    ('Капучино', 'Еспресо з молочною піною.', 65, 'Кава'),
    ('Флет-вайт', 'Подвійний еспресо з ніжним молоком.', 75, 'Кава'),
    ('Чізкейк', 'Вершковий чізкейк з ягідним соусом.', 95, 'Десерти'),
    ('Шоколадний брауні', 'Щільний брауні з горіхами.', 80, 'Десерти'),
    ('Панна-кота', 'Вершкова панна-кота з ягідним соусом.', 85, 'Десерти'),
    ('Мигдалевий круасан', 'Круасан з кремом франжипан.', 70, 'Випічка'),
    ('Чай із м’ятою', 'Свіжа м’ята та мед.', 50, 'Чай та напої'),
]

SEED_CUSTOMERS = [
    ('Олена Коваль', '+380501112233', 'olena@example.com'),
    ('Іван Петренко', '+380672223344', None),
]


def get_db():
    """Повертає з’єднання з БД для поточного запиту (створює, якщо його ще немає)."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row            # рядки читаються як row['name']
        g.db.execute('PRAGMA foreign_keys = ON')  # SQLite за замовчуванням не перевіряє зовнішні ключі
    return g.db


def close_db(exception=None):
    """Закриває з’єднання після завершення запиту (підключається через teardown_appcontext)."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(sql, args=(), one=False):
    """SELECT-запит. Повертає список рядків або один рядок (one=True), або None."""
    cursor = get_db().execute(sql, args)
    rows = cursor.fetchall()
    cursor.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute_db(sql, args=()):
    """INSERT / UPDATE / DELETE з автоматичним commit. Повертає id доданого рядка."""
    db = get_db()
    cursor = db.execute(sql, args)
    db.commit()
    last_id = cursor.lastrowid
    cursor.close()
    return last_id

# Колонки, додані до вже існуючих таблиць після першого релізу схеми.
# CREATE TABLE IF NOT EXISTS не змінює стару таблицю, тому додаємо їх через ALTER TABLE.
MIGRATIONS = [
    ('orders', 'promo_code', 'TEXT'),
    ('orders', 'discount', 'REAL NOT NULL DEFAULT 0'),
]


def migrate_db(db):
    """Додає відсутні колонки в старий db.sqlite, не видаляючи наявні дані."""
    for table, column, definition in MIGRATIONS:
        columns = [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
        if columns and column not in columns:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    db.commit()


def init_db():
    """Створює таблиці зі schema.sql, оновлює стару схему і додає тестові дані, якщо таблиці порожні."""
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf-8'))
    migrate_db(db)

    if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        db.executemany(
            'INSERT INTO products (name, description, price, category) VALUES (?, ?, ?, ?)',
            SEED_PRODUCTS,
        )
    if db.execute('SELECT COUNT(*) FROM customers').fetchone()[0] == 0:
        db.executemany(
            'INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)',
            SEED_CUSTOMERS,
        )
    db.commit()
