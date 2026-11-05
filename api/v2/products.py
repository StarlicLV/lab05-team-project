"""API v2: товари (префікс /api/v2/products).

Відмінності від v1: список із пагінацією, сортуванням і розширеними фільтрами,
відповіді загорнуті в {"data": ..., "meta": ...}.
"""
from flask import Blueprint, jsonify, request

from models import query_db
from ..errors import ApiError
from ..utils import get_int_arg, get_float_arg, get_bool_arg
from ..v1.products import product_to_dict, get_product_or_404

bp = Blueprint('v2_products', __name__, url_prefix='/products')

SORT_FIELDS = {'id', 'name', 'price', 'category'}  # білий список полів сортування


@bp.route('', methods=['GET'])
def list_products():
    """Список товарів із пагінацією, сортуванням і фільтрами
    ---
    tags:
      - Products (v2)
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
    page = get_int_arg('page', 1)
    per_page = get_int_arg('per_page', 10, maximum=100)
    min_price = get_float_arg('min_price')
    max_price = get_float_arg('max_price')
    available = get_bool_arg('available')

    sort = request.args.get('sort', 'id').strip() or 'id'
    direction = 'DESC' if sort.startswith('-') else 'ASC'
    sort_field = sort.lstrip('-')
    if sort_field not in SORT_FIELDS:
        raise ApiError(400, 'Параметр sort має бути одним із: ' + ', '.join(sorted(SORT_FIELDS)))

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
        'data': [product_to_dict(r) for r in rows],
        'meta': {'page': page, 'per_page': per_page, 'total': total, 'pages': pages},
    }), 200


@bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Отримати товар (формат v2: дані в полі data)
    ---
    tags:
      - Products (v2)
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
    return jsonify({'data': product_to_dict(get_product_or_404(product_id))}), 200
