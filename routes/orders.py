"""Замовлення: оформлення з кошика, статуси, промокоди (рівень 3), адмінка.

Кошик читається з session['cart'] = {product_id: quantity}. Статуси — models.ORDER_STATUSES.
"""
import re
import sqlite3

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from models import ORDER_STATUSES, execute_db, get_db, query_db

bp = Blueprint('orders', __name__)


# ---------------------------------------------------------------------------
# Допоміжні функції
# ---------------------------------------------------------------------------

def menu_url():
    """Адреса меню. Після того як частина Б перенесе меню в blueprint shop, endpoint
    стане 'shop.menu'; поки його немає, використовується старий 'menu' з app.py."""
    if 'shop.menu' in current_app.view_functions:
        return url_for('shop.menu')
    return url_for('menu')


def load_cart():
    """Перетворює session['cart'] на список позицій і загальну суму.

    Ключі в сесії — рядки, тому product_id перетворюємо на int. Товари, яких немає в БД або
    які зараз недоступні, пропускаємо. Ціну завжди беремо з БД, а не з сесії (користувач
    не може її підробити).
    """
    cart = session.get('cart', {})
    items = []
    for product_id, quantity in cart.items():
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity < 1:
            continue
        product = query_db(
            'SELECT id, name, price, is_available FROM products WHERE id = ?',
            (product_id,), one=True)
        if product is None or not product['is_available']:
            continue
        items.append({
            'id': product['id'],
            'name': product['name'],
            'price': product['price'],
            'quantity': quantity,
            'sum': round(product['price'] * quantity, 2),
        })
    subtotal = round(sum(item['sum'] for item in items), 2)
    return items, subtotal


def normalize_phone(raw):
    """Прибирає пробіли, дужки й дефіси: '+38 (050) 111-22-33' -> '+380501112233'.
    Завдяки цьому той самий номер у різному записі знаходить того ж клієнта."""
    return re.sub(r'[\s\-()]', '', raw)


def find_active_promo(code):
    """Повертає активний промокод (рядок БД) або None. Код порівнюється без урахування регістру."""
    return query_db(
        'SELECT * FROM promo_codes WHERE code = ? AND is_active = 1',
        (code.strip().upper(),), one=True)


def validate_checkout(form):
    """Перевіряє форму оформлення. Повертає (errors, phone, promo)."""
    errors = {}
    if not form['name']:
        errors['name'] = 'Вкажіть ім’я.'
    phone = normalize_phone(form['phone'])
    if not re.fullmatch(r'\+?\d{10,13}', phone):
        errors['phone'] = 'Введіть коректний номер телефону (10–13 цифр), наприклад +380501112233.'
    if form['email'] and '@' not in form['email']:
        errors['email'] = 'Email має містити символ @.'
    if not form['address']:
        errors['address'] = 'Вкажіть адресу доставки.'

    promo = None
    if form['promo_code']:
        promo = find_active_promo(form['promo_code'])
        if promo is None:
            errors['promo_code'] = 'Такого активного промокоду немає.'
    return errors, phone, promo


def create_order(form, phone, items, subtotal, promo):
    """Створює клієнта (якщо його ще немає), замовлення й позиції В ОДНІЙ ТРАНЗАКЦІЇ.

    Усі INSERT виконуються через одне з'єднання, а commit() викликається один раз наприкінці.
    Якщо щось зламається посередині, rollback() скасує все, і напівствореного замовлення
    (замовлення без позицій) у базі не лишиться.
    """
    db = get_db()
    try:
        customer = db.execute('SELECT id FROM customers WHERE phone = ?', (phone,)).fetchone()
        if customer:
            customer_id = customer['id']
        else:
            cursor = db.execute(
                'INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)',
                (form['name'], phone, form['email'] or None))
            customer_id = cursor.lastrowid

        discount = round(subtotal * promo['discount_percent'] / 100, 2) if promo else 0
        total = round(subtotal - discount, 2)

        cursor = db.execute(
            'INSERT INTO orders (customer_id, address, comment, total, promo_code, discount) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (customer_id, form['address'], form['comment'], total,
             promo['code'] if promo else None, discount))
        order_id = cursor.lastrowid

        db.executemany(
            'INSERT INTO order_items (order_id, product_id, quantity, price_at_order) '
            'VALUES (?, ?, ?, ?)',
            [(order_id, i['id'], i['quantity'], i['price']) for i in items])

        db.commit()
    except Exception:
        db.rollback()
        raise
    return order_id


# ---------------------------------------------------------------------------
# Публічна частина: оформлення замовлення
# ---------------------------------------------------------------------------

@bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    items, subtotal = load_cart()
    if not items:
        flash('Ваш кошик порожній. Додайте щось із меню.')
        return redirect(menu_url())

    form = {'name': '', 'phone': '', 'email': '', 'address': '', 'comment': '', 'promo_code': ''}
    errors = {}
    promo = None

    if request.method == 'POST':
        form = {key: request.form.get(key, '').strip() for key in form}
        errors, phone, promo = validate_checkout(form)
        if not errors:
            order_id = create_order(form, phone, items, subtotal, promo)
            session.pop('cart', None)               # кошик очищаємо після успішного збереження
            session['last_order_id'] = order_id     # лише цей користувач бачить сторінку підтвердження
            return redirect(url_for('orders.confirmation', order_id=order_id))

    # Якщо код дійсний, показуємо знижку у зведенні (корисно й при повторному показі форми)
    discount = round(subtotal * promo['discount_percent'] / 100, 2) if promo else 0
    return render_template('orders/checkout.html', items=items, subtotal=subtotal,
                           discount=discount, total=round(subtotal - discount, 2),
                           promo=promo, form=form, errors=errors)


@bp.route('/order/<int:order_id>/done')
def confirmation(order_id):
    # Підтвердження бачить лише той, хто щойно оформив це замовлення (id зберігається в сесії)
    if session.get('last_order_id') != order_id:
        abort(404)
    order = query_db(
        'SELECT o.*, c.name AS customer_name FROM orders o '
        'JOIN customers c ON c.id = o.customer_id WHERE o.id = ?', (order_id,), one=True)
    if order is None:
        abort(404)
    order_items = query_db(
        'SELECT p.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order AS line_total '
        'FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?',
        (order_id,))
    return render_template('orders/confirmation.html', order=order, order_items=order_items,
                           statuses=ORDER_STATUSES)


# ---------------------------------------------------------------------------
# Адмінка: замовлення
# ---------------------------------------------------------------------------

@bp.route('/admin/orders')
def admin_orders():
    status = request.args.get('status', '')
    sql = ('SELECT o.id, o.status, o.total, o.created_at, c.name AS customer_name, c.phone '
           'FROM orders o JOIN customers c ON c.id = o.customer_id')
    args = ()
    # Фільтр додаємо лише якщо статус є в довіднику; саме значення передаємо через «?»
    if status in ORDER_STATUSES:
        sql += ' WHERE o.status = ?'
        args = (status,)
    else:
        status = ''
    sql += ' ORDER BY o.created_at DESC, o.id DESC'
    orders = query_db(sql, args)
    return render_template('admin/orders_list.html', orders=orders,
                           statuses=ORDER_STATUSES, current_status=status)


@bp.route('/admin/orders/<int:order_id>')
def admin_order_detail(order_id):
    order = query_db(
        'SELECT o.*, c.name AS customer_name, c.phone, c.email FROM orders o '
        'JOIN customers c ON c.id = o.customer_id WHERE o.id = ?', (order_id,), one=True)
    if order is None:
        abort(404)
    order_items = query_db(
        'SELECT p.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order AS line_total '
        'FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.order_id = ?',
        (order_id,))
    return render_template('admin/order_detail.html', order=order, order_items=order_items,
                           statuses=ORDER_STATUSES)


@bp.route('/admin/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    status = request.form.get('status', '')
    if status not in ORDER_STATUSES:
        flash('Невідомий статус замовлення.')
    elif query_db('SELECT id FROM orders WHERE id = ?', (order_id,), one=True) is None:
        abort(404)
    else:
        execute_db('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        flash(f'Статус замовлення №{order_id} змінено на «{ORDER_STATUSES[status]}».')
    return redirect(url_for('orders.admin_order_detail', order_id=order_id))


# ---------------------------------------------------------------------------
# Адмінка: промокоди (рівень 3)
# ---------------------------------------------------------------------------

@bp.route('/admin/promo')
def admin_promo():
    promos = query_db('SELECT * FROM promo_codes ORDER BY id DESC')
    return render_template('admin/promo_codes.html', promos=promos)


@bp.route('/admin/promo/add', methods=['POST'])
def add_promo():
    code = request.form.get('code', '').strip().upper()
    percent_raw = request.form.get('discount_percent', '').strip()

    if not re.fullmatch(r'[A-Z0-9_-]{3,20}', code):
        flash('Код має містити 3–20 символів: латинські літери, цифри, «-» або «_».')
    elif not percent_raw.isdigit() or not 1 <= int(percent_raw) <= 100:
        flash('Знижка має бути цілим числом від 1 до 100.')
    else:
        try:
            execute_db('INSERT INTO promo_codes (code, discount_percent) VALUES (?, ?)',
                       (code, int(percent_raw)))
            flash(f'Промокод {code} додано.')
        except sqlite3.IntegrityError:
            flash(f'Промокод {code} уже існує.')
    return redirect(url_for('orders.admin_promo'))


@bp.route('/admin/promo/<int:promo_id>/toggle', methods=['POST'])
def toggle_promo(promo_id):
    promo = query_db('SELECT * FROM promo_codes WHERE id = ?', (promo_id,), one=True)
    if promo is None:
        abort(404)
    execute_db('UPDATE promo_codes SET is_active = ? WHERE id = ?', (0 if promo['is_active'] else 1, promo_id))
    flash(f'Промокод {promo["code"]} {"вимкнено" if promo["is_active"] else "увімкнено"}.')
    return redirect(url_for('orders.admin_promo'))
