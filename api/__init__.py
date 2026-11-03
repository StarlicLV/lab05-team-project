"""REST API кав'ярні (лабораторна робота 05).

Структура:
    api/errors.py        формат помилок, ApiError, JSON-обробники
    api/utils.py         читання JSON, валідація полів, пагінація
    api/v1/              products.py, orders.py, customers.py
    api/v2/              customers.py (розширена версія)

Підключення в app.py:  register_api(app)
"""
from flask import Blueprint, jsonify

from .errors import register_error_handlers
from .v1 import api_v1
from .v2 import api_v2

root = Blueprint('api_root', __name__)


@root.route('/api')
@root.route('/api/')
def api_index():
    """Точка входу в API: перелік доступних версій."""
    return jsonify({
        'name': 'Coffee shop API',
        'versions': {'v1': '/api/v1', 'v2': '/api/v2'},
    }), 200


def register_api(app):
    register_error_handlers(app)
    for blueprint in (root, api_v1, api_v2):
        app.register_blueprint(blueprint)

    # TODO (учасник C, рівень 2): підключити Swagger для сторінки /apidocs/
    #   from flasgger import Swagger
    #   Swagger(app, template={...})
