"""API v2: клієнти (відповідальний: teamlead).

Відмінності від v1:
    * список із пагінацією, пошуком і сортуванням, відповідь у конверті {"data": [...], "meta": {...}};
    * картка клієнта містить вкладені замовлення та суму витрат.
Створення, зміна й видалення працюють так само, як у v1 (використовуйте /api/v1/customers).
"""
from flask import Blueprint, jsonify, request

from models import query_db
from ..utils import get_int_arg, get_enum_arg
from ..v1.customers import CUSTOMER_SQL, get_customer_or_404

bp = Blueprint('v2_customers', __name__, url_prefix='/customers')

# Дозволені поля сортування: значення йдуть у SQL лише зі цього списку (захист від ін'єкцій)
SORT_FIELDS = {
    'created_at': 'c.created_at',
    'name': 'c.name',
    'orders_count': 'orders_count',
}


@bp.route('', methods=['GET'])
def list_customers():
    """Список клієнтів із пагінацією, пошуком і сортуванням
    ---
    tags:
      - Customers (v2)
    parameters:
      - {name: page, in: query, type: integer, default: 1, description: Номер сторінки}
      - {name: per_page, in: query, type: integer, default: 10, description: 'Розмір сторінки (1-100)'}
      - {name: q, in: query, type: string, description: Пошук за іменем, телефоном або email}
      - name: sort
        in: query
        type: string
        enum: [created_at, name, orders_count]
        default: created_at
      - name: order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
    responses:
      200:
        description: Сторінка клієнтів і метадані пагінації
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                $ref: '#/definitions/Customer'
            meta:
              type: object
              properties:
                page: {type: integer, example: 1}
                per_page: {type: integer, example: 10}
                total: {type: integer, example: 25}
                pages: {type: integer, example: 3}
      400:
        description: Некоректний параметр запиту
    """
    page = get_int_arg('page', 1)
    per_page = get_int_arg('per_page', 10, maximum=100)
    sort = get_enum_arg('sort', tuple(SORT_FIELDS), 'created_at')
    order = get_enum_arg('order', ('asc', 'desc'), 'desc')
    q = request.args.get('q', '').strip()

    where = ''
    params = []
    if q:
        where = 'WHERE c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ? '
        params = [f'%{q}%'] * 3

    total = query_db(f'SELECT COUNT(*) AS n FROM customers c {where}', tuple(params), one=True)['n']
    rows = query_db(
        f'{CUSTOMER_SQL}{where}GROUP BY c.id '
        f'ORDER BY {SORT_FIELDS[sort]} {order.upper()}, c.id DESC LIMIT ? OFFSET ?',
        tuple(params) + (per_page, (page - 1) * per_page))

    pages = (total + per_page - 1) // per_page
    return jsonify({
        'data': [dict(r) for r in rows],
        'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': pages},
    }), 200


@bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Картка клієнта з замовленнями та сумою витрат
    ---
    tags:
      - Customers (v2)
    parameters:
      - name: customer_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Клієнт, його замовлення (без скасованих у total_spent)
        schema:
          type: object
          properties:
            id: {type: integer}
            name: {type: string}
            phone: {type: string}
            email: {type: string, x-nullable: true}
            created_at: {type: string}
            orders_count: {type: integer}
            total_spent: {type: number, example: 380.0}
            orders:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  status: {type: string}
                  total: {type: number}
                  created_at: {type: string}
      404:
        description: Клієнта не знайдено
    """
    customer = get_customer_or_404(customer_id)
    orders = [dict(r) for r in query_db(
        'SELECT id, status, total, created_at FROM orders WHERE customer_id = ? ORDER BY id DESC',
        (customer_id,))]
    customer['orders'] = orders
    # скасовані замовлення в суму витрат не входять
    customer['total_spent'] = round(sum(o['total'] for o in orders if o['status'] != 'cancelled'), 2)
    return jsonify(customer), 200
