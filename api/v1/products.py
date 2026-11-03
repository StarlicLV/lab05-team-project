"""API v1: товари.

TODO (мінімум 5 endpoints, префікс /api/v1/products):
    GET     /          список товарів (можна додати ?category= і ?q=, як у меню)
    GET     /<id>      один товар (404, якщо немає)
    POST    /          створити товар (валідація: name, price >= 0, category, is_available)
    PUT або PATCH /<id>  оновити товар
    DELETE  /<id>      видалити (409, якщо товар є в замовленнях: у схемі ON DELETE RESTRICT)

Що вже готово в api/utils.py: get_json_body(), check_string(), check_number(), raise_if_errors().
Помилки: raise ApiError(404, 'Товар не знайдено') -> JSON {"error": ..., "status": 404}.
Зразок оформлення (код + docstring для flasgger) дивіться в api/v1/customers.py.
"""
from flask import Blueprint

bp = Blueprint('v1_products', __name__, url_prefix='/products')
