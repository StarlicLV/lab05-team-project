"""API v1: замовлення та промокоди (відповідальний: Мельник Віталій).

Адреси (префікс /api/v1/orders):
    GET     /                список замовлень (необовʼязковий фільтр ?status=)
    GET     /<id>            замовлення з позиціями
    POST    /                створити замовлення (необовʼязковий promo_code)
    PATCH   /<id>/status     змінити статус замовлення
"""
from flask import Blueprint, jsonify, request, url_for

from models import ORDER_STATUSES, get_db, query_db
from ..errors import ApiError
from ..utils import get_json_body, raise_if_errors, check_string

bp = Blueprint('v1_orders', __name__, url_prefix='/orders')

ORDER_SQL = (
    'SELECT o.id, o.customer_id, c.name AS customer_name, o.status, o.address, o.comment, '
    'o.promo_code, o.discount, o.total, o.created_at '
    'FROM orders o JOIN customers c ON c.id = o.customer_id '
)


def get_order_or_404(order_id):
    """Замовлення разом із позиціями (JOIN order_items + products)."""
    row = query_db(ORDER_SQL + 'WHERE o.id = ?', (order_id,), one=True)
    if row is None:
        raise ApiError(404, 'Замовлення не знайдено')
    order = dict(row)
    items = query_db(
        'SELECT oi.product_id, p.name, oi.quantity, oi.price_at_order, '
        'ROUND(oi.quantity * oi.price_at_order, 2) AS line_total '
        'FROM order_items oi JOIN products p ON p.id = oi.product_id '
        'WHERE oi.order_id = ? ORDER BY oi.id', (order_id,))
    order['items'] = [dict(i) for i in items]
    return order


def is_int(value):
    """bool є підкласом int, тому true/false відсікаємо окремо."""
    return isinstance(value, int) and not isinstance(value, bool)


def validate_order(data):
    """Перевіряє тіло POST. Повертає (customer_id, address, comment, promo_code, items).
    items — словник {product_id: quantity}; однакові товари об'єднуються."""
    errors = {}

    customer_id = data.get('customer_id')
    if customer_id is None:
        errors['customer_id'] = 'Поле обовʼязкове'
    elif not is_int(customer_id) or customer_id < 1:
        errors['customer_id'] = 'Має бути цілим числом більше 0'

    address = check_string(data, 'address', errors, max_len=255)
    comment = check_string(data, 'comment', errors, required=False, max_len=500) or ''
    promo_code = check_string(data, 'promo_code', errors, required=False, max_len=20)
    promo_code = promo_code.upper() if promo_code else None

    items = {}
    raw_items = data.get('items')
    if raw_items is None:
        errors['items'] = 'Поле обовʼязкове'
    elif not isinstance(raw_items, list) or not raw_items:
        errors['items'] = 'Має бути непорожнім списком позицій'
    else:
        for index, item in enumerate(raw_items):
            key = f'items[{index}]'
            if not isinstance(item, dict):
                errors[key] = 'Позиція має бути обʼєктом {product_id, quantity}'
                continue
            product_id, quantity = item.get('product_id'), item.get('quantity')
            if not is_int(product_id) or product_id < 1:
                errors[f'{key}.product_id'] = 'Має бути цілим числом більше 0'
            if not is_int(quantity) or quantity < 1:
                errors[f'{key}.quantity'] = 'Має бути цілим числом більше 0'
            if f'{key}.product_id' not in errors and f'{key}.quantity' not in errors:
                items[product_id] = items.get(product_id, 0) + quantity

    raise_if_errors(errors)
    return customer_id, address, comment, promo_code, items


# ---------- Читання ----------

@bp.route('', methods=['GET'])
def list_orders():
    """Список замовлень
    ---
    tags:
      - Orders (v1)
    parameters:
      - name: status
        in: query
        type: string
        required: false
        enum: [new, preparing, delivering, done, cancelled]
        description: Показати лише замовлення з таким статусом
    responses:
      200:
        description: Список замовлень (найновіші першими)
        schema:
          type: object
          properties:
            count: {type: integer, example: 1}
            orders:
              type: array
              items:
                $ref: '#/definitions/Order'
      400:
        description: Невідомий статус у фільтрі
    definitions:
      Order:
        type: object
        properties:
          id: {type: integer, example: 1}
          customer_id: {type: integer, example: 1}
          customer_name: {type: string, example: Олена Коваль}
          status: {type: string, example: new}
          address: {type: string, example: 'Київ, вул. Хрещатик 1'}
          comment: {type: string, example: ''}
          promo_code: {type: string, example: SWEET10, x-nullable: true}
          discount: {type: number, example: 19.0}
          total: {type: number, example: 171.0}
          created_at: {type: string, example: '2026-11-03 10:00:00'}
      OrderDetail:
        allOf:
          - $ref: '#/definitions/Order'
          - type: object
            properties:
              items:
                type: array
                items:
                  type: object
                  properties:
                    product_id: {type: integer, example: 4}
                    name: {type: string, example: Чізкейк}
                    quantity: {type: integer, example: 2}
                    price_at_order: {type: number, example: 95.0}
                    line_total: {type: number, example: 190.0}
    """
    status = request.args.get('status')
    if status:
        if status not in ORDER_STATUSES:
            raise ApiError(400, 'Параметр status має бути одним із: ' + ', '.join(ORDER_STATUSES))
        rows = query_db(ORDER_SQL + 'WHERE o.status = ? ORDER BY o.id DESC', (status,))
    else:
        rows = query_db(ORDER_SQL + 'ORDER BY o.id DESC')
    return jsonify({'count': len(rows), 'orders': [dict(r) for r in rows]}), 200


@bp.route('/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Одне замовлення з позиціями
    ---
    tags:
      - Orders (v1)
    parameters:
      - name: order_id
        in: path
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Замовлення з позиціями
        schema:
          $ref: '#/definitions/OrderDetail'
      404:
        description: Замовлення не знайдено
    """
    return jsonify(get_order_or_404(order_id)), 200


# ---------- Створення ----------

@bp.route('', methods=['POST'])
def create_order():
    """Створити замовлення (з необовʼязковим промокодом)
    ---
    tags:
      - Orders (v1)
    consumes:
      - application/json
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [customer_id, address, items]
          properties:
            customer_id: {type: integer, example: 1}
            address: {type: string, example: 'Київ, вул. Хрещатик 1'}
            comment: {type: string, example: Без цукру}
            promo_code: {type: string, example: SWEET10}
            items:
              type: array
              items:
                type: object
                required: [product_id, quantity]
                properties:
                  product_id: {type: integer, example: 4}
                  quantity: {type: integer, example: 2}
    responses:
      201:
        description: Замовлення створено (адреса в заголовку Location)
        schema:
          $ref: '#/definitions/OrderDetail'
      400:
        description: Помилка валідації, недоступний товар або недійсний промокод
      404:
        description: Клієнта чи товар не знайдено
      415:
        description: Тіло запиту не є JSON
    """
    customer_id, address, comment, promo_code, items = validate_order(get_json_body())

    if query_db('SELECT id FROM customers WHERE id = ?', (customer_id,), one=True) is None:
        raise ApiError(404, 'Клієнта не знайдено')

    # Ціни беремо з БД (не з запиту), щоб клієнт не міг підставити свою ціну
    lines = []
    subtotal = 0.0
    for product_id, quantity in items.items():
        product = query_db('SELECT id, name, price, is_available FROM products WHERE id = ?',
                           (product_id,), one=True)
        if product is None:
            raise ApiError(404, f'Товар з id {product_id} не знайдено')
        if not product['is_available']:
            raise ApiError(400, 'Товар недоступний для замовлення',
                           {'items': f'«{product["name"]}» зараз недоступний'})
        lines.append((product_id, quantity, product['price']))
        subtotal += product['price'] * quantity

    discount = 0.0
    if promo_code:
        promo = query_db('SELECT discount_percent FROM promo_codes WHERE code = ? AND is_active = 1',
                         (promo_code,), one=True)
        if promo is None:
            raise ApiError(400, 'Недійсний промокод',
                           {'promo_code': 'Промокод не існує або вимкнений'})
        discount = round(subtotal * promo['discount_percent'] / 100, 2)
    total = round(subtotal - discount, 2)

    # Замовлення й позиції — в одній транзакції (один commit)
    db = get_db()
    try:
        cursor = db.execute(
            'INSERT INTO orders (customer_id, address, comment, total, promo_code, discount) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (customer_id, address, comment, total, promo_code, discount))
        order_id = cursor.lastrowid
        db.executemany(
            'INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES (?, ?, ?, ?)',
            [(order_id, pid, qty, price) for pid, qty, price in lines])
        db.commit()
    except Exception:
        db.rollback()
        raise

    response = jsonify(get_order_or_404(order_id))
    response.status_code = 201
    response.headers['Location'] = url_for('api_v1.v1_orders.get_order', order_id=order_id)
    return response


# ---------- Зміна статусу ----------

@bp.route('/<int:order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    """Змінити статус замовлення
    ---
    tags:
      - Orders (v1)
    consumes:
      - application/json
    parameters:
      - name: order_id
        in: path
        type: integer
        required: true
        example: 1
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: [status]
          properties:
            status:
              type: string
              enum: [new, preparing, delivering, done, cancelled]
              example: preparing
    responses:
      200:
        description: Оновлене замовлення
        schema:
          $ref: '#/definitions/OrderDetail'
      400:
        description: Невідомий статус
      404:
        description: Замовлення не знайдено
      415:
        description: Тіло запиту не є JSON
    """
    get_order_or_404(order_id)
    data = get_json_body()
    status = data.get('status')
    if not isinstance(status, str) or status not in ORDER_STATUSES:
        raise ApiError(400, 'Помилка валідації даних',
                       {'status': 'Має бути одним із: ' + ', '.join(ORDER_STATUSES)})
    db = get_db()
    db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    db.commit()
    return jsonify(get_order_or_404(order_id)), 200
