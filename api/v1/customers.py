"""API v1: клієнти (відповідальний: teamlead).

Адреси (префікс /api/v1/customers):
    GET     /                  список клієнтів
    GET     /<id>              один клієнт
    GET     /<id>/orders       замовлення клієнта
    POST    /                  створити клієнта
    PUT     /<id>              повна заміна (усі поля)
    PATCH   /<id>              часткове оновлення (лише передані поля)
    DELETE  /<id>              видалити (409, якщо у клієнта є замовлення)
"""
import sqlite3

from flask import Blueprint, jsonify, url_for

from models import query_db, execute_db
from ..errors import ApiError
from ..utils import (get_json_body, raise_if_errors, check_string, check_phone,
                     check_email)

bp = Blueprint('v1_customers', __name__, url_prefix='/customers')

# Однаковий SELECT для списку й одного клієнта: LEFT JOIN, щоб клієнти без замовлень теж були
CUSTOMER_SQL = (
    'SELECT c.id, c.name, c.phone, c.email, c.created_at, COUNT(o.id) AS orders_count '
    'FROM customers c LEFT JOIN orders o ON o.customer_id = c.id '
)


def get_customer_or_404(customer_id):
    row = query_db(CUSTOMER_SQL + 'WHERE c.id = ? GROUP BY c.id', (customer_id,), one=True)
    if row is None:
        raise ApiError(404, 'Клієнта не знайдено')
    return dict(row)


def phone_taken(phone, exclude_id=None):
    row = query_db('SELECT id FROM customers WHERE phone = ? AND id != ?',
                   (phone, exclude_id or 0), one=True)
    return row is not None


def validate_customer(data, partial=False):
    """Повертає словник очищених полів. partial=True (PATCH): перевіряються лише передані поля."""
    errors = {}
    clean = {}
    if not partial or 'name' in data:
        clean['name'] = check_string(data, 'name', errors, max_len=100)
    if not partial or 'phone' in data:
        clean['phone'] = check_phone(data, 'phone', errors)
    if not partial or 'email' in data:
        clean['email'] = check_email(data, 'email', errors)
    raise_if_errors(errors)
    return clean


# ---------- Читання ----------

@bp.route('', methods=['GET'])
def list_customers():
    """Список клієнтів
    ---
    tags:
      - Customers (v1)
    responses:
      200:
        description: Список усіх клієнтів (найновіші першими)
        schema:
          type: object
          properties:
            customers:
              type: array
              items:
                $ref: '#/definitions/Customer'
    definitions:
      Customer:
        type: object
        properties:
          id: {type: integer, example: 1}
          name: {type: string, example: Олена Коваль}
          phone: {type: string, example: '+380501112233'}
          email: {type: string, example: olena@example.com, x-nullable: true}
          created_at: {type: string, example: '2026-11-03 10:00:00'}
          orders_count: {type: integer, example: 2}
    """
    rows = query_db(CUSTOMER_SQL + 'GROUP BY c.id ORDER BY c.id DESC')
    return jsonify({'customers': [dict(r) for r in rows]}), 200


@bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Отримати клієнта за id
    ---
    tags:
      - Customers (v1)
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Дані клієнта
        schema:
          $ref: '#/definitions/Customer'
      404:
        description: Клієнта не знайдено
    """
    return jsonify(get_customer_or_404(customer_id)), 200


@bp.route('/<int:customer_id>/orders', methods=['GET'])
def get_customer_orders(customer_id):
    """Замовлення клієнта
    ---
    tags:
      - Customers (v1)
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Замовлення клієнта (найновіші першими)
        schema:
          type: object
          properties:
            customer_id: {type: integer, example: 1}
            orders:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  status: {type: string, example: new}
                  total: {type: number, example: 190.0}
                  created_at: {type: string}
      404:
        description: Клієнта не знайдено
    """
    get_customer_or_404(customer_id)
    rows = query_db('SELECT id, status, total, created_at FROM orders '
                    'WHERE customer_id = ? ORDER BY id DESC', (customer_id,))
    return jsonify({'customer_id': customer_id, 'orders': [dict(r) for r in rows]}), 200


# ---------- Створення ----------

@bp.route('', methods=['POST'])
def create_customer():
    """Створити клієнта
    ---
    tags:
      - Customers (v1)
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [name, phone]
          properties:
            name: {type: string, example: Марія Шевченко}
            phone: {type: string, example: '+380931234567'}
            email: {type: string, example: maria@example.com}
    responses:
      201:
        description: Клієнта створено (адреса нового ресурсу в заголовку Location)
        schema:
          $ref: '#/definitions/Customer'
      400:
        description: Помилка валідації
      409:
        description: Клієнт із таким телефоном уже існує
      415:
        description: Тіло запиту не є JSON
    """
    clean = validate_customer(get_json_body())
    if phone_taken(clean['phone']):
        raise ApiError(409, 'Клієнт із таким телефоном уже існує')
    new_id = execute_db('INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)',
                        (clean['name'], clean['phone'], clean['email']))
    response = jsonify(get_customer_or_404(new_id))
    response.status_code = 201
    response.headers['Location'] = url_for('api_v1.v1_customers.get_customer', customer_id=new_id)
    return response


# ---------- Оновлення ----------

def _update(customer_id, partial):
    existing = get_customer_or_404(customer_id)
    clean = validate_customer(get_json_body(), partial=partial)
    if partial:
        # PATCH: незадані поля лишаються як були
        merged = {k: existing[k] for k in ('name', 'phone', 'email')}
        merged.update(clean)
        clean = merged
    if phone_taken(clean['phone'], exclude_id=customer_id):
        raise ApiError(409, 'Клієнт із таким телефоном уже існує')
    execute_db('UPDATE customers SET name = ?, phone = ?, email = ? WHERE id = ?',
               (clean['name'], clean['phone'], clean['email'], customer_id))
    return jsonify(get_customer_or_404(customer_id)), 200


@bp.route('/<int:customer_id>', methods=['PUT'])
def replace_customer(customer_id):
    """Повністю замінити дані клієнта (PUT)
    ---
    tags:
      - Customers (v1)
    consumes:
      - application/json
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [name, phone]
          properties:
            name: {type: string, example: Олена Коваль}
            phone: {type: string, example: '+380501112233'}
            email: {type: string, example: new@example.com}
    responses:
      200:
        description: Оновлений клієнт
        schema:
          $ref: '#/definitions/Customer'
      400:
        description: Помилка валідації
      404:
        description: Клієнта не знайдено
      409:
        description: Телефон уже використовує інший клієнт
    """
    return _update(customer_id, partial=False)


@bp.route('/<int:customer_id>', methods=['PATCH'])
def update_customer(customer_id):
    """Частково оновити клієнта (PATCH)
    ---
    tags:
      - Customers (v1)
    consumes:
      - application/json
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string, example: Олена Іванівна Коваль}
            phone: {type: string}
            email: {type: string}
    responses:
      200:
        description: Оновлений клієнт
        schema:
          $ref: '#/definitions/Customer'
      400:
        description: Помилка валідації
      404:
        description: Клієнта не знайдено
      409:
        description: Телефон уже використовує інший клієнт
    """
    return _update(customer_id, partial=True)


# ---------- Видалення ----------

@bp.route('/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """Видалити клієнта
    ---
    tags:
      - Customers (v1)
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
    responses:
      204:
        description: Клієнта видалено (тіла відповіді немає)
      404:
        description: Клієнта не знайдено
      409:
        description: У клієнта є замовлення, видалити його не можна
    """
    customer = get_customer_or_404(customer_id)
    if customer['orders_count'] > 0:
        raise ApiError(409, 'Не можна видалити клієнта, у якого є замовлення')
    try:
        execute_db('DELETE FROM customers WHERE id = ?', (customer_id,))
    except sqlite3.IntegrityError:
        # страховка: ON DELETE RESTRICT у схемі БД
        raise ApiError(409, 'Не можна видалити клієнта, у якого є замовлення')
    return '', 204
