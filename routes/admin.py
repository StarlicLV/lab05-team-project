"""Головна сторінка адмін-панелі.

Розділи адмінки живуть у файлах їхніх власників (feedback.py, shop.py, orders.py, customers.py).
"""
from flask import Blueprint, render_template

from models import query_db

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/')
def index():
    counts = {
        'feedback': query_db('SELECT COUNT(*) AS n FROM feedback', one=True)['n'],
        'products': query_db('SELECT COUNT(*) AS n FROM products', one=True)['n'],
        'orders': query_db('SELECT COUNT(*) AS n FROM orders', one=True)['n'],
        'customers': query_db('SELECT COUNT(*) AS n FROM customers', one=True)['n'],
    }
    return render_template('admin/index.html', counts=counts)
