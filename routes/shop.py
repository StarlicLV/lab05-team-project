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


# ======================================================================
# ЛАБОРАТОРНА 05. REST API для товарів (версії v1 і v2)
# Усе в цьому ж файлі; окремо нічого підключати не треба.
# Документація Swagger: http://127.0.0.1:5000/apidocs/ (потрібен пакет flasgger)
# ======================================================================
from flask import jsonify

try:  # якщо flasgger не встановлено, API працює, просто без сторінки документації
    from flasgger import Swagger
except ImportError:
    Swagger = None

SWAGGER_TEMPLATE = {
    'swagger': '2.0',
    'info': {
        'title': 'API кав\'ярні: товари',
        'description': 'REST API для керування товарами (меню кав\'ярні з десертами). '
                       'Версія v1 - базова, версія v2 - з пагінацією, сортуванням і розширеними фільтрами.',
        'version': '2.0',
    },
    'tags': [
        {'name': 'Товари v1', 'description': 'Базові операції CRUD'},
        {'name': 'Товари v2', 'description': 'Список із пагінацією, сортуванням і фільтрами'},
    ],
    'definitions': {
        'Product': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer', 'example': 1},
                'name': {'type': 'string', 'example': 'Тірамісу'},
                'description': {'type': 'string', 'example': 'Класичний італійський десерт'},
                'price': {'type': 'number', 'example': 95.0},
                'category': {'type': 'string', 'example': 'Десерти'},
                'is_available': {'type': 'boolean', 'example': True},
            },
        },
        'ProductInput': {
            'type': 'object',
            'required': ['name', 'price', 'category'],
            'properties': {
                'name': {'type': 'string', 'example': 'Лате'},
                'description': {'type': 'string', 'example': 'Кава з молоком'},
                'price': {'type': 'number', 'example': 70},
                'category': {'type': 'string', 'example': 'Кава'},
                'is_available': {'type': 'boolean', 'example': True},
            },
        },
        'Error': {
            'type': 'object',
            'properties': {
                'error': {'type': 'string', 'example': 'Товар не знайдено'},
                'status': {'type': 'integer', 'example': 404},
                'details': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
    },
}


@shop.record_once
def _init_swagger(state):
    """Підключає Swagger UI (/apidocs/), якщо flasgger встановлено і ще не підключений."""
    if Swagger is not None and 'flasgger' not in state.app.blueprints:
        Swagger(state.app, template=SWAGGER_TEMPLATE)


# ---------- Допоміжні функції API ----------

def _api_error(status, message, details=None):
    """Єдиний формат помилок: {"error": ..., "status": ..., "details": [...]}"""
    body = {'error': message, 'status': status}
    if details:
        body['details'] = details
    return jsonify(body), status


def _product_to_dict(row):
    d = dict(row)
    d['price'] = float(d['price'])
    d['is_available'] = bool(d['is_available'])
    return d


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        and not math.isnan(v) and not math.isinf(v)


def _api_validate(data, partial=False):
    """Валідація вхідних даних. partial=True для PATCH (перевіряються лише передані поля).
    Повертає (очищені дані, список помилок)."""
    errors, clean = [], {}

    if 'name' in data or not partial:
        v = data.get('name')
        if not isinstance(v, str) or not v.strip():
            errors.append("Поле name обов'язкове і має бути непорожнім рядком")
        elif len(v.strip()) > 100:
            errors.append('Поле name має бути не довшим за 100 символів')
        else:
            clean['name'] = v.strip()

    if 'category' in data or not partial:
        v = data.get('category')
        if not isinstance(v, str) or not v.strip():
            errors.append("Поле category обов'язкове і має бути непорожнім рядком")
        else:
            clean['category'] = v.strip()

    if 'price' in data or not partial:
        v = data.get('price')
        if not _is_number(v) or v < 0:
            errors.append("Поле price обов'язкове і має бути числом не менше нуля")
        else:
            clean['price'] = float(v)

    if 'description' in data:
        v = data.get('description')
        if not isinstance(v, str):
            errors.append('Поле description має бути рядком')
        else:
            clean['description'] = v.strip()
    elif not partial:
        clean['description'] = ''

    if 'is_available' in data:
        v = data.get('is_available')
        if isinstance(v, bool) or v in (0, 1):
            clean['is_available'] = 1 if v else 0
        else:
            errors.append('Поле is_available має бути true або false')
    elif not partial:
        clean['is_available'] = 1

    return clean, errors


def _json_body():
    data = request.get_json(silent=True)  # None, якщо тіло запиту не є JSON
    return data if isinstance(data, dict) else None


def _find_product(product_id):
    return query_db('SELECT * FROM products WHERE id = ?', (product_id,), one=True)


def _bool_param(name):
    """Читає ?name=true/false/1/0. Повертає (значення або None, помилка або None)."""
    raw = request.args.get(name)
    if raw is None or raw == '':
        return None, None
    if raw.lower() in ('1', 'true'):
        return 1, None
    if raw.lower() in ('0', 'false'):
        return 0, None
    return None, 'Параметр %s має бути true або false' % name


# ---------- Обробка помилок у форматі JSON (лише для адрес /api/) ----------

@shop.app_errorhandler(400)
def _api_400(e):
    return _api_error(400, 'Некоректний запит') if request.path.startswith('/api/') else e


@shop.app_errorhandler(404)
def _api_404(e):
    return _api_error(404, 'Ресурс не знайдено') if request.path.startswith('/api/') else e


@shop.app_errorhandler(405)
def _api_405(e):
    return _api_error(405, 'Метод не дозволений для цього ресурсу') \
        if request.path.startswith('/api/') else e


@shop.app_errorhandler(500)
def _api_500(e):
    return _api_error(500, 'Внутрішня помилка сервера') if request.path.startswith('/api/') else e


# ---------- API v1 ----------

@shop.route('/api/v1/products', methods=['GET'])
def api_v1_list_products():
    """Список товарів
    ---
    tags:
      - Товари v1
    parameters:
      - name: category
        in: query
        type: string
        description: Фільтр за категорією
      - name: q
        in: query
        type: string
        description: Пошук за частиною назви
      - name: available
        in: query
        type: boolean
        description: Лише доступні (true) або лише вимкнені (false)
    responses:
      200:
        description: Список товарів
        schema:
          type: object
          properties:
            count:
              type: integer
            products:
              type: array
              items:
                $ref: '#/definitions/Product'
      400:
        description: Некоректний параметр
        schema:
          $ref: '#/definitions/Error'
    """
    available, err = _bool_param('available')
    if err:
        return _api_error(400, err)

    sql, params = 'SELECT * FROM products WHERE 1 = 1', []
    category = request.args.get('category', '').strip()
    q = request.args.get('q', '').strip()
    if category:
        sql += ' AND category = ?'
        params.append(category)
    if q:
        sql += ' AND name LIKE ?'
        params.append('%' + q + '%')
    if available is not None:
        sql += ' AND is_available = ?'
        params.append(available)
    sql += ' ORDER BY id'

    products = [_product_to_dict(r) for r in query_db(sql, tuple(params))]
    return jsonify({'count': len(products), 'products': products}), 200


@shop.route('/api/v1/products/categories', methods=['GET'])
def api_v1_categories():
    """Список категорій товарів
    ---
    tags:
      - Товари v1
    responses:
      200:
        description: Унікальні категорії
        schema:
          type: object
          properties:
            categories:
              type: array
              items:
                type: string
    """
    rows = query_db('SELECT DISTINCT category FROM products ORDER BY category')
    return jsonify({'categories': [r['category'] for r in rows]}), 200


@shop.route('/api/v1/products/<int:product_id>', methods=['GET'])
def api_v1_get_product(product_id):
    """Отримати товар за ідентифікатором
    ---
    tags:
      - Товари v1
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Дані товару
        schema:
          $ref: '#/definitions/Product'
      404:
        description: Товар не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    row = _find_product(product_id)
    if row is None:
        return _api_error(404, 'Товар не знайдено')
    return jsonify(_product_to_dict(row)), 200


@shop.route('/api/v1/products', methods=['POST'])
def api_v1_create_product():
    """Створити товар
    ---
    tags:
      - Товари v1
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/ProductInput'
    responses:
      201:
        description: Товар створено
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації або тіло запиту не є JSON
        schema:
          $ref: '#/definitions/Error'
    """
    data = _json_body()
    if data is None:
        return _api_error(400, 'Тіло запиту має бути JSON-об\'єктом')
    clean, errors = _api_validate(data)
    if errors:
        return _api_error(400, 'Помилка валідації', errors)

    new_id = execute_db(
        'INSERT INTO products (name, description, price, category, is_available) '
        'VALUES (?, ?, ?, ?, ?)',
        (clean['name'], clean['description'], clean['price'],
         clean['category'], clean['is_available']))
    response = jsonify(_product_to_dict(_find_product(new_id)))
    response.status_code = 201
    response.headers['Location'] = '/api/v1/products/%d' % new_id
    return response


@shop.route('/api/v1/products/<int:product_id>', methods=['PUT'])
def api_v1_replace_product(product_id):
    """Повністю замінити товар
    ---
    tags:
      - Товари v1
    consumes:
      - application/json
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          $ref: '#/definitions/ProductInput'
    responses:
      200:
        description: Товар оновлено
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Товар не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    if _find_product(product_id) is None:
        return _api_error(404, 'Товар не знайдено')
    data = _json_body()
    if data is None:
        return _api_error(400, 'Тіло запиту має бути JSON-об\'єктом')
    clean, errors = _api_validate(data)
    if errors:
        return _api_error(400, 'Помилка валідації', errors)

    execute_db(
        'UPDATE products SET name = ?, description = ?, price = ?, category = ?, '
        'is_available = ? WHERE id = ?',
        (clean['name'], clean['description'], clean['price'],
         clean['category'], clean['is_available'], product_id))
    return jsonify(_product_to_dict(_find_product(product_id))), 200


@shop.route('/api/v1/products/<int:product_id>', methods=['PATCH'])
def api_v1_patch_product(product_id):
    """Частково оновити товар (лише передані поля)
    ---
    tags:
      - Товари v1
    consumes:
      - application/json
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            price:
              type: number
              example: 99.5
            is_available:
              type: boolean
              example: false
    responses:
      200:
        description: Товар оновлено
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації або немає полів для оновлення
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Товар не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    if _find_product(product_id) is None:
        return _api_error(404, 'Товар не знайдено')
    data = _json_body()
    if data is None:
        return _api_error(400, 'Тіло запиту має бути JSON-об\'єктом')
    clean, errors = _api_validate(data, partial=True)
    if errors:
        return _api_error(400, 'Помилка валідації', errors)
    if not clean:
        return _api_error(400, 'Немає полів для оновлення',
                          ['Допустимі поля: name, description, price, category, is_available'])

    # Назви стовпців беруться лише з нашого очищеного словника (не від користувача),
    # а самі значення передаються через ?
    set_clause = ', '.join('%s = ?' % column for column in clean)
    execute_db('UPDATE products SET ' + set_clause + ' WHERE id = ?',
               tuple(clean.values()) + (product_id,))
    return jsonify(_product_to_dict(_find_product(product_id))), 200


@shop.route('/api/v1/products/<int:product_id>', methods=['DELETE'])
def api_v1_delete_product(product_id):
    """Видалити товар
    ---
    tags:
      - Товари v1
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      204:
        description: Товар видалено (тіла відповіді немає)
      404:
        description: Товар не знайдено
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Товар є в замовленнях, видалити не можна (вимкніть його через PATCH is_available=false)
        schema:
          $ref: '#/definitions/Error'
    """
    if _find_product(product_id) is None:
        return _api_error(404, 'Товар не знайдено')
    try:
        execute_db('DELETE FROM products WHERE id = ?', (product_id,))
    except sqlite3.IntegrityError:  # ON DELETE RESTRICT
        return _api_error(409, 'Товар є в замовленнях, його не можна видалити',
                          ['Вимкніть товар: PATCH з {"is_available": false}'])
    return '', 204


# ---------- API v2 (пагінація, сортування, розширені фільтри) ----------

V2_SORT_FIELDS = {'id', 'name', 'price', 'category'}  # білий список полів сортування


@shop.route('/api/v2/products', methods=['GET'])
def api_v2_list_products():
    """Список товарів із пагінацією, сортуванням і фільтрами
    ---
    tags:
      - Товари v2
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: Номер сторінки (від 1)
      - name: per_page
        in: query
        type: integer
        default: 10
        description: Кількість на сторінці (1-100)
      - name: sort
        in: query
        type: string
        default: id
        description: Поле сортування (id, name, price, category); мінус на початку = за спаданням, наприклад -price
      - name: q
        in: query
        type: string
        description: Пошук за частиною назви
      - name: category
        in: query
        type: string
      - name: min_price
        in: query
        type: number
      - name: max_price
        in: query
        type: number
      - name: available
        in: query
        type: boolean
    responses:
      200:
        description: Сторінка товарів
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                $ref: '#/definitions/Product'
            meta:
              type: object
              properties:
                page:
                  type: integer
                per_page:
                  type: integer
                total:
                  type: integer
                pages:
                  type: integer
      400:
        description: Некоректний параметр
        schema:
          $ref: '#/definitions/Error'
    """
    errors = []

    def int_param(name, default, low, high=None):
        raw = request.args.get(name)
        if raw in (None, ''):
            return default
        try:
            value = int(raw)
        except ValueError:
            errors.append('Параметр %s має бути цілим числом' % name)
            return default
        if value < low or (high is not None and value > high):
            errors.append('Параметр %s поза допустимим діапазоном' % name)
            return default
        return value

    def float_param(name):
        raw = request.args.get(name)
        if raw in (None, ''):
            return None
        try:
            return float(raw)
        except ValueError:
            errors.append('Параметр %s має бути числом' % name)
            return None

    page = int_param('page', 1, 1)
    per_page = int_param('per_page', 10, 1, 100)
    min_price = float_param('min_price')
    max_price = float_param('max_price')
    available, bool_err = _bool_param('available')
    if bool_err:
        errors.append(bool_err)

    sort = request.args.get('sort', 'id').strip() or 'id'
    direction = 'DESC' if sort.startswith('-') else 'ASC'
    sort_field = sort.lstrip('-')
    if sort_field not in V2_SORT_FIELDS:
        errors.append('Параметр sort має бути одним із: ' + ', '.join(sorted(V2_SORT_FIELDS)))

    if errors:
        return _api_error(400, 'Некоректні параметри запиту', errors)

    where, params = ' WHERE 1 = 1', []
    category = request.args.get('category', '').strip()
    q = request.args.get('q', '').strip()
    if category:
        where += ' AND category = ?'
        params.append(category)
    if q:
        where += ' AND name LIKE ?'
        params.append('%' + q + '%')
    if min_price is not None:
        where += ' AND price >= ?'
        params.append(min_price)
    if max_price is not None:
        where += ' AND price <= ?'
        params.append(max_price)
    if available is not None:
        where += ' AND is_available = ?'
        params.append(available)

    total = query_db('SELECT COUNT(*) AS n FROM products' + where, tuple(params), one=True)['n']
    # sort_field і direction перевірені за білим списком, тому безпечні
    rows = query_db(
        'SELECT * FROM products' + where +
        ' ORDER BY %s %s LIMIT ? OFFSET ?' % (sort_field, direction),
        tuple(params) + (per_page, (page - 1) * per_page))

    pages = (total + per_page - 1) // per_page
    return jsonify({
        'data': [_product_to_dict(r) for r in rows],
        'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': pages},
    }), 200


@shop.route('/api/v2/products/<int:product_id>', methods=['GET'])
def api_v2_get_product(product_id):
    """Отримати товар (формат v2: дані в полі data)
    ---
    tags:
      - Товари v2
    parameters:
      - name: product_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Дані товару
        schema:
          type: object
          properties:
            data:
              $ref: '#/definitions/Product'
      404:
        description: Товар не знайдено
        schema:
          $ref: '#/definitions/Error'
    """
    row = _find_product(product_id)
    if row is None:
        return _api_error(404, 'Товар не знайдено')
    return jsonify({'data': _product_to_dict(row)}), 200


# ---------- Запасна сторінка документації (якщо flasgger не встановлено) ----------

API_DOCS = [
    ('GET', '/api/v1/products', 'Список товарів. Параметри: category, q, available', '200, 400',
     'GET /api/v1/products?category=Кава', '{"count": 1, "products": [{"id": 2, "name": "Лате", "price": 70.0, ...}]}'),
    ('GET', '/api/v1/products/categories', 'Список категорій', '200',
     'GET /api/v1/products/categories', '{"categories": ["Десерти", "Кава"]}'),
    ('GET', '/api/v1/products/<id>', 'Один товар', '200, 404',
     'GET /api/v1/products/1', '{"id": 1, "name": "Тірамісу", "price": 90.0, "category": "Десерти", "is_available": true}'),
    ('POST', '/api/v1/products', 'Створити товар (name, price, category обов\'язкові)', '201, 400',
     '{"name": "Лате", "price": 70, "category": "Кава"}', '201 Created + Location; {"id": 4, "name": "Лате", ...}'),
    ('PUT', '/api/v1/products/<id>', 'Повна заміна товару', '200, 400, 404',
     '{"name": "Лате", "price": 75, "category": "Кава", "is_available": true}', '{"id": 2, "price": 75.0, ...}'),
    ('PATCH', '/api/v1/products/<id>', 'Часткове оновлення (лише передані поля)', '200, 400, 404',
     '{"price": 99.5, "is_available": false}', '{"id": 2, "price": 99.5, "is_available": false, ...}'),
    ('DELETE', '/api/v1/products/<id>', 'Видалити товар (409, якщо він є в замовленнях)', '204, 404, 409',
     'DELETE /api/v1/products/3', '204 No Content (без тіла)'),
    ('GET', '/api/v2/products', 'Список із пагінацією: page, per_page, sort (-price), q, category, min_price, max_price, available', '200, 400',
     'GET /api/v2/products?page=1&per_page=5&sort=-price', '{"data": [...], "meta": {"page": 1, "per_page": 5, "total": 12, "pages": 3}}'),
    ('GET', '/api/v2/products/<id>', 'Один товар (формат v2)', '200, 404',
     'GET /api/v2/products/1', '{"data": {"id": 1, "name": "Тірамісу", ...}}'),
]

DOCS_TEMPLATE = r"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Документація API товарів</title>
<style>
 :root { --bg:#fff; --fg:#1f2937; --card:#f3f4f6; --line:#d1d5db; --accent:#b45309; }
 @media (prefers-color-scheme: dark) { :root { --bg:#111827; --fg:#e5e7eb; --card:#1f2937; --line:#374151; --accent:#fbbf24; } }
 body { background:var(--bg); color:var(--fg); font-family:system-ui,sans-serif; margin:0; padding:16px; max-width:900px; margin:auto; }
 .ep { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; margin:12px 0; }
 .m { font-weight:700; color:var(--accent); } code,pre { word-break:break-all; white-space:pre-wrap; }
 h1 { font-size:1.5rem; } small { opacity:.8; }
</style></head><body>
<h1>API товарів кав'ярні</h1>
<p>Формат даних: JSON. Версії: <b>v1</b> (базова) і <b>v2</b> (пагінація, сортування, фільтри).
Помилки повертаються як <code>{"error": "...", "status": 400, "details": [...]}</code>.</p>
{% for m, url, desc, codes, req, resp in docs %}
<div class="ep">
  <div><span class="m">{{ m }}</span> <code>{{ url }}</code></div>
  <div>{{ desc }}</div>
  <small>Коди відповідей: {{ codes }}</small>
  <div><small>Запит:</small><pre>{{ req }}</pre></div>
  <div><small>Відповідь:</small><pre>{{ resp }}</pre></div>
</div>
{% endfor %}
</body></html>
"""

if Swagger is None:
    @shop.route('/apidocs/')
    def api_docs_fallback():
        return render_template_string(DOCS_TEMPLATE, docs=API_DOCS)
