"""API v1: товари (префікс /api/v1/products).

    GET     /              список (фільтри: ?category=, ?q=, ?available=true|false)
    GET     /categories    список категорій
    GET     /<id>          один товар
    POST    /              створити
    PUT     /<id>          повна заміна
    PATCH   /<id>          часткове оновлення
    DELETE  /<id>          видалити (409, якщо товар є в замовленнях)
"""
import sqlite3

from flask import Blueprint, jsonify, request, url_for

from models import query_db, execute_db
from ..errors import ApiError
from ..utils import (get_json_body, raise_if_errors, check_string, check_number,
                     get_bool_arg)

bp = Blueprint('v1_products', __name__, url_prefix='/products')


# ---------- Допоміжні функції (їх використовує і api/v2/products.py) ----------

def product_to_dict(row):
    d = dict(row)
    d['price'] = float(d['price'])
    d['is_available'] = bool(d['is_available'])
    return d


def find_product(product_id):
    return query_db('SELECT * FROM products WHERE id = ?', (product_id,), one=True)


def get_product_or_404(product_id):
    row = find_product(product_id)
    if row is None:
        raise ApiError(404, 'Товар не знайдено')
    return row


def validate_product(data, partial=False):
    """Валідація вхідних даних. partial=True для PATCH (перевіряються лише передані поля)."""
    errors, clean = {}, {}

    if not partial or 'name' in data:
        clean['name'] = check_string(data, 'name', errors, max_len=100)
    if not partial or 'category' in data:
        clean['category'] = check_string(data, 'category', errors, max_len=100)
    if not partial or 'price' in data:
        price = check_number(data, 'price', errors, minimum=0)
        clean['price'] = float(price) if price is not None else None

    if 'description' in data:
        description = check_string(data, 'description', errors, required=False, max_len=1000)
        clean['description'] = description if description is not None else ''
    elif not partial:
        clean['description'] = ''

    if 'is_available' in data:
        value = data['is_available']
        if isinstance(value, bool) or value in (0, 1):
            clean['is_available'] = 1 if value else 0
        else:
            errors['is_available'] = 'Має бути true або false'
    elif not partial:
        clean['is_available'] = 1

    raise_if_errors(errors)
    return clean


# ---------- Читання ----------

@bp.route('', methods=['GET'])
def list_products():
    """Список товарів
    ---
    tags:
      - Products (v1)
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
    available = get_bool_arg('available')

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

    products = [product_to_dict(r) for r in query_db(sql, tuple(params))]
    return jsonify({'count': len(products), 'products': products}), 200


@bp.route('/categories', methods=['GET'])
def list_categories():
    """Список категорій товарів
    ---
    tags:
      - Products (v1)
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


@bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Отримати товар за ідентифікатором
    ---
    tags:
      - Products (v1)
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
    return jsonify(product_to_dict(get_product_or_404(product_id))), 200


# ---------- Створення й зміна ----------

@bp.route('', methods=['POST'])
def create_product():
    """Створити товар
    ---
    tags:
      - Products (v1)
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
        description: Товар створено (адреса в заголовку Location)
        schema:
          $ref: '#/definitions/Product'
      400:
        description: Помилка валідації або тіло запиту не є JSON-обʼєктом
        schema:
          $ref: '#/definitions/Error'
      415:
        description: Тіло запиту не є JSON
        schema:
          $ref: '#/definitions/Error'
    """
    clean = validate_product(get_json_body())
    new_id = execute_db(
        'INSERT INTO products (name, description, price, category, is_available) '
        'VALUES (?, ?, ?, ?, ?)',
        (clean['name'], clean['description'], clean['price'],
         clean['category'], clean['is_available']))
    response = jsonify(product_to_dict(find_product(new_id)))
    response.status_code = 201
    response.headers['Location'] = url_for('api_v1.v1_products.get_product', product_id=new_id)
    return response


@bp.route('/<int:product_id>', methods=['PUT'])
def replace_product(product_id):
    """Повністю замінити товар
    ---
    tags:
      - Products (v1)
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
    get_product_or_404(product_id)
    clean = validate_product(get_json_body())
    execute_db(
        'UPDATE products SET name = ?, description = ?, price = ?, category = ?, '
        'is_available = ? WHERE id = ?',
        (clean['name'], clean['description'], clean['price'],
         clean['category'], clean['is_available'], product_id))
    return jsonify(product_to_dict(find_product(product_id))), 200


@bp.route('/<int:product_id>', methods=['PATCH'])
def patch_product(product_id):
    """Частково оновити товар (лише передані поля)
    ---
    tags:
      - Products (v1)
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
    get_product_or_404(product_id)
    clean = validate_product(get_json_body(), partial=True)
    if not clean:
        raise ApiError(400, 'Немає полів для оновлення', {
            'body': 'Допустимі поля: name, description, price, category, is_available'})

    # Назви стовпців беруться лише з нашого очищеного словника (не від користувача),
    # а самі значення передаються через ?
    set_clause = ', '.join('%s = ?' % column for column in clean)
    execute_db('UPDATE products SET ' + set_clause + ' WHERE id = ?',
               tuple(clean.values()) + (product_id,))
    return jsonify(product_to_dict(find_product(product_id))), 200


# ---------- Видалення ----------

@bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Видалити товар
    ---
    tags:
      - Products (v1)
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
    get_product_or_404(product_id)
    try:
        execute_db('DELETE FROM products WHERE id = ?', (product_id,))
    except sqlite3.IntegrityError:  # ON DELETE RESTRICT
        raise ApiError(409, 'Товар є в замовленнях, його не можна видалити', {
            'hint': 'Вимкніть товар: PATCH з {"is_available": false}'})
    return '', 204
