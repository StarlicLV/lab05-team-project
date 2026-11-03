"""API версії 2: /api/v2/... (розширена версія: пагінація, пошук, вкладені дані)."""
from flask import Blueprint

from . import customers

api_v2 = Blueprint('api_v2', __name__, url_prefix='/api/v2')

api_v2.register_blueprint(customers.bp)
