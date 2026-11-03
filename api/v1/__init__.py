"""API версії 1: /api/v1/..."""
from flask import Blueprint

from . import customers, orders, products

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Кожен учасник працює у своєму файлі, тут їх лише підключаємо
for module in (products, orders, customers):
    api_v1.register_blueprint(module.bp)
