"""Клієнти (рівень 2): CRUD у адмін-панелі."""
from flask import Blueprint, render_template

from models import query_db

bp = Blueprint('customers', __name__)


@bp.route('/admin/customers')
def admin_customers():
    # LEFT JOIN, щоб у списку були й клієнти без замовлень (для них orders_count = 0)
    customers = query_db(
        'SELECT c.id, c.name, c.phone, c.email, c.created_at, '
        '       COUNT(o.id) AS orders_count '
        'FROM customers c LEFT JOIN orders o ON o.customer_id = c.id '
        'GROUP BY c.id '
        'ORDER BY c.id DESC'
    )
    return render_template('admin/customers_list.html', customers=customers)
