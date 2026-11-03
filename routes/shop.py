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
        errors.append('Назва не може бути порожньою.')
    price = None
    try:
        price = float(price_raw)
        if math.isnan(price) or math.isinf(price) or price < 0:
            errors.append('Ціна має бути числом не менше нуля.')
    except ValueError:
        errors.append('Ціна має бути числом не менше нуля.')

    is_available = 1 if form.get('is_available') else 0
    return (name, description, price, category, is_available), errors


def _render_admin(edit_product=None, form_data=None):
    products = query_db('SELECT * FROM products ORDER BY category, name')
    edit_product = dict(edit_product) if edit_product is not None else None
    form_data = dict(form_data) if form_data is not None else None
    return render_template_string(ADMIN_TEMPLATE, products=products,
                                  edit_product=edit_product, form_data=form_data)


@shop.route('/admin/products')
def admin_products():
    return _render_admin()


@shop.route('/admin/products/add', methods=['POST'])
def add_product():
    data, errors = _validate_product(request.form)
    if errors:
        for e in errors:
            flash(e, 'error')
        return _render_admin(form_data=request.form)
    execute_db(
        'INSERT INTO products (name, description, price, category, is_available) '
        'VALUES (?, ?, ?, ?, ?)', data)
    flash('Товар додано.', 'success')
    return redirect(url_for('shop.admin_products'))


@shop.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    product = query_db('SELECT * FROM products WHERE id = ?', (product_id,), one=True)
    if product is None:
        flash('Товар не знайдено.', 'error')
        return redirect(url_for('shop.admin_products'))

    if request.method == 'POST':
        data, errors = _validate_product(request.form)
        if errors:
            for e in errors:
                flash(e, 'error')
            return _render_admin(edit_product=product, form_data=request.form)
        execute_db(
            'UPDATE products SET name = ?, description = ?, price = ?, category = ?, '
            'is_available = ? WHERE id = ?', data + (product_id,))
        flash('Товар оновлено.', 'success')
        return redirect(url_for('shop.admin_products'))

    return _render_admin(edit_product=product)


@shop.route('/admin/products/<int:product_id>/toggle', methods=['POST'])
def toggle_product(product_id):
    execute_db(
        'UPDATE products SET is_available = CASE is_available WHEN 1 THEN 0 ELSE 1 END '
        'WHERE id = ?', (product_id,))
    flash('Доступність товару змінено.', 'success')
    return redirect(url_for('shop.admin_products'))


@shop.route('/admin/products/<int:product_id>/delete', methods=['POST'])
def delete_product(product_id):
    try:
        execute_db('DELETE FROM products WHERE id = ?', (product_id,))
        flash('Товар видалено.', 'success')
    except sqlite3.IntegrityError:
        # ON DELETE RESTRICT: товар є в замовленнях
        flash('Цей товар є в замовленнях, тому його не можна видалити. '
              'Вимкніть його (перемикач доступності) — він зникне з меню.', 'error')
    return redirect(url_for('shop.admin_products'))


# ---------- Шаблони (вбудовані, окремі файли не потрібні) ----------

MENU_TEMPLATE = r"""{% extends 'base.html' %}
{% block __BLOCK__ %}
<div class="max-w-6xl mx-auto px-4 py-8">
  <h1 class="text-3xl font-bold mb-6 text-gray-900 dark:text-gray-100">Меню</h1>

  <form method="get" action="{{ url_for('shop.menu') }}" class="flex flex-col sm:flex-row gap-3 mb-8">
    <input type="text" name="q" value="{{ q }}" placeholder="Пошук за назвою..."
           class="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2">
    <select name="category"
            class="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2">
      <option value="">Усі категорії</option>
      {% for c in categories %}
      <option value="{{ c['category'] }}" {% if c['category'] == selected_category %}selected{% endif %}>{{ c['category'] }}</option>
      {% endfor %}
    </select>
    <button type="submit" class="rounded bg-amber-600 hover:bg-amber-700 text-white px-4 py-2">Знайти</button>
    {% if q or selected_category %}
    <a href="{{ url_for('shop.menu') }}" class="rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 px-4 py-2 text-center">Скинути</a>
    {% endif %}
  </form>

  {% if total == 0 %}
  <p class="text-center text-gray-600 dark:text-gray-400 py-12 text-lg">Нічого не знайдено.</p>
  {% endif %}

  {% for category, items in grouped.items() %}
  <h2 class="text-2xl font-semibold mt-8 mb-4 text-gray-800 dark:text-gray-200">{{ category }}</h2>
  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {% for p in items %}
    <div class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 flex flex-col">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ p['name'] }}</h3>
      <p class="text-sm text-gray-600 dark:text-gray-400 mt-1 flex-1">{{ p['description'] }}</p>
      <div class="flex items-center justify-between mt-4">
        <span class="text-lg font-bold text-amber-700 dark:text-amber-400">{{ '%.2f'|format(p['price']) }} ₴</span>
        <form method="post" action="{{ cart_url(p['id']) }}">
          <button type="submit" class="rounded bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 text-sm">Додати в кошик</button>
        </form>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endfor %}
</div>
{% endblock %}
"""

ADMIN_TEMPLATE = r"""{% extends 'admin/base_admin.html' %}
{% block admin_content %}
{% set f = form_data or edit_product or {} %}
<h1 class="text-2xl font-bold mb-4 text-gray-900 dark:text-gray-100">Товари</h1>

<form method="post"
      action="{{ url_for('shop.edit_product', product_id=edit_product['id']) if edit_product else url_for('shop.add_product') }}"
      class="grid gap-3 md:grid-cols-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 mb-8">
  <h2 class="md:col-span-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
    {{ 'Редагування товару' if edit_product else 'Додати товар' }}
  </h2>
  <input name="name" value="{{ f['name'] if f.get('name') is not none else '' }}" placeholder="Назва" required
         class="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-3 py-2">
  <input name="category" value="{{ f['category'] if f.get('category') is not none else '' }}" placeholder="Категорія"
         class="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-3 py-2">
  <input name="price" value="{{ f['price'] if f.get('price') is not none else '' }}" placeholder="Ціна" required
         class="rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-3 py-2">
  <label class="flex items-center gap-2 text-gray-800 dark:text-gray-200">
    <input type="checkbox" name="is_available" value="1"
           {% if (not f) or f.get('is_available') in (1, '1') %}checked{% endif %}> Доступний
  </label>
  <textarea name="description" rows="2" placeholder="Опис"
            class="md:col-span-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-3 py-2">{{ f['description'] if f.get('description') is not none else '' }}</textarea>
  <div class="md:col-span-2 flex gap-2">
    <button type="submit" class="rounded bg-amber-600 hover:bg-amber-700 text-white px-4 py-2">
      {{ 'Зберегти' if edit_product else 'Додати' }}
    </button>
    {% if edit_product %}
    <a href="{{ url_for('shop.admin_products') }}" class="rounded border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 px-4 py-2">Скасувати</a>
    {% endif %}
  </div>
</form>

<div class="overflow-x-auto">
<table class="w-full text-sm text-left text-gray-800 dark:text-gray-200">
  <thead class="bg-gray-100 dark:bg-gray-700">
    <tr><th class="p-2">ID</th><th class="p-2">Назва</th><th class="p-2">Категорія</th>
        <th class="p-2">Ціна</th><th class="p-2">Статус</th><th class="p-2">Дії</th></tr>
  </thead>
  <tbody>
  {% for p in products %}
    <tr class="border-b border-gray-200 dark:border-gray-700">
      <td class="p-2">{{ p['id'] }}</td>
      <td class="p-2">{{ p['name'] }}</td>
      <td class="p-2">{{ p['category'] }}</td>
      <td class="p-2">{{ '%.2f'|format(p['price']) }} ₴</td>
      <td class="p-2">{{ 'Доступний' if p['is_available'] else 'Вимкнено' }}</td>
      <td class="p-2 flex flex-wrap gap-2">
        <a href="{{ url_for('shop.edit_product', product_id=p['id']) }}" class="rounded bg-blue-600 text-white px-2 py-1">Ред.</a>
        <form method="post" action="{{ url_for('shop.toggle_product', product_id=p['id']) }}">
          <button class="rounded bg-gray-600 text-white px-2 py-1">{{ 'Вимкнути' if p['is_available'] else 'Увімкнути' }}</button>
        </form>
        <form method="post" action="{{ url_for('shop.delete_product', product_id=p['id']) }}"
              onsubmit="return confirm('Видалити товар?');">
          <button class="rounded bg-red-600 text-white px-2 py-1">Видалити</button>
        </form>
      </td>
    </tr>
  {% else %}
    <tr><td colspan="6" class="p-4 text-center">Товарів немає.</td></tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% endblock %}
"""
