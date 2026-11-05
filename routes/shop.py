"""Частина Б: меню з БД, адмінка товарів, пошук і фільтрація."""
import math
import sqlite3

from werkzeug.routing import BuildError

from flask import Blueprint, render_template_string, request, current_app, redirect, url_for, flash

from models import query_db, execute_db

shop = Blueprint('shop', __name__)
bp = shop_bp = shop_blueprint = shop  # аліаси, щоб підійшло будь-яке ім'я в app.py


def _block_name():
    """Знаходить назву блоку контенту в base.html (щоб не залежати від вгадування)."""
    try:
        names = list(current_app.jinja_env.get_template('base.html').blocks)
    except Exception:
        return 'content'
    for n in ('content', 'main', 'body', 'page_content', 'main_content'):
        if n in names:
            return n
    return names[-1] if names else 'content'


def _cart_url(product_id):
    """Посилання на додавання в кошик (працює, навіть якщо кошик ще не підключено)."""
    try:
        from flask import url_for
        return url_for('cart.add_to_cart', product_id=product_id)
    except BuildError:
        return '/cart/add/%d' % product_id


@shop.before_app_request
def _use_new_menu_for_old_endpoint():
    """Якщо в app.py лишився старий маршрут меню (endpoint 'menu'), показуємо нове меню з БД."""
    if request.endpoint == 'menu':
        return menu()


# ---------- Публічне меню ----------

@shop.route('/menu')
def menu():
    """Меню з БД: пошук (?q=) і фільтр за категорією (?category=)."""
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    sql = 'SELECT * FROM products WHERE is_available = 1'
    params = []
    if q:
        sql += ' AND name LIKE ?'
        params.append('%' + q + '%')          # параметр, а не f-рядок (захист від SQL-ін'єкцій)
    if category:
        sql += ' AND category = ?'
        params.append(category)
    sql += ' ORDER BY category, name'

    products = query_db(sql, tuple(params))
    categories = query_db(
        'SELECT DISTINCT category FROM products WHERE is_available = 1 ORDER BY category')

    # групування за категорією
    grouped = {}
    for p in products:
        grouped.setdefault(p['category'], []).append(p)

    return render_template_string(MENU_TEMPLATE.replace('__BLOCK__', _block_name()), cart_url=_cart_url, grouped=grouped, categories=categories,
                           q=q, selected_category=category, total=len(products))


# ---------- Адмінка товарів ----------

def _validate_product(form):
    """Повертає (дані, список помилок)."""
    name = form.get('name', '').strip()
    description = form.get('description', '').strip()
    category = form.get('category', '').strip()
    price_raw = form.get('price', '').strip().replace(',', '.')
    errors = []

    if not name:
        errors.append('Назва не може бути по
