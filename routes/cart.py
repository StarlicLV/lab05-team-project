"""Кошик. Формат у сесії: session['cart'] = {product_id: quantity}.

Ключі в сесії зберігаються як рядки, тому при записі використовуємо str(product_id),
а при читанні перетворюємо на int.
"""
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from models import query_db

bp = Blueprint('cart', __name__)

MAX_QUANTITY = 99


def menu_url():
    """Адреса меню: 'shop.menu' після роботи частини Б, до того — старий 'menu' з app.py."""
    if 'shop.menu' in current_app.view_functions:
        return url_for('shop.menu')
    return url_for('menu')


def save_cart(cart):
    session['cart'] = cart
    session.modified = True  # Flask не помічає змін усередині словника сам


def parse_quantity(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@bp.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = query_db('SELECT id, name, is_available FROM products WHERE id = ?',
                       (product_id,), one=True)
    if product is None or not product['is_available']:
        flash('Цей товар недоступний.')
        return redirect(url_for('cart.view_cart'))

    quantity = max(1, parse_quantity(request.form.get('quantity'), 1))
    cart = dict(session.get('cart', {}))
    key = str(product_id)
    cart[key] = min(cart.get(key, 0) + quantity, MAX_QUANTITY)  # якщо товар уже є, збільшуємо кількість
    save_cart(cart)

    flash(f'«{product["name"]}» додано в кошик.')
    return redirect(url_for('cart.view_cart'))


@bp.route('/cart')
def view_cart():
    cart = dict(session.get('cart', {}))
    items = []
    total = 0
    pruned = False

    for key, quantity in list(cart.items()):
        try:
            product_id = int(key)
            quantity = int(quantity)
        except (TypeError, ValueError):
            del cart[key]
            pruned = True
            continue
        # Ціну завжди беремо з БД, а не з сесії
        product = query_db('SELECT id, name, price, is_available FROM products WHERE id = ?',
                           (product_id,), one=True)
        if product is None or not product['is_available'] or quantity < 1:
            # Товар видалили або вимкнули після того, як його додали в кошик
            del cart[key]
            pruned = True
            continue
        line_total = round(product['price'] * quantity, 2)
        total += line_total
        items.append({'id': product['id'], 'name': product['name'], 'price': product['price'],
                      'quantity': quantity, 'sum': line_total})

    if pruned:
        save_cart(cart)
        flash('Деякі товари стали недоступні й були прибрані з кошика.')

    return render_template('cart.html', items=items, total=round(total, 2),
                           max_quantity=MAX_QUANTITY, menu_url=menu_url())


@bp.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    cart = dict(session.get('cart', {}))
    key = str(product_id)
    if key not in cart:
        flash('Цього товару немає в кошику.')
        return redirect(url_for('cart.view_cart'))

    quantity = parse_quantity(request.form.get('quantity'), None)
    if quantity is None:
        flash('Кількість має бути цілим числом.')
    elif quantity <= 0:
        del cart[key]
        save_cart(cart)
        flash('Позицію видалено з кошика.')
    else:
        cart[key] = min(quantity, MAX_QUANTITY)
        save_cart(cart)
        flash('Кількість оновлено.')
    return redirect(url_for('cart.view_cart'))


@bp.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = dict(session.get('cart', {}))
    if cart.pop(str(product_id), None) is not None:
        save_cart(cart)
        flash('Позицію видалено з кошика.')
    return redirect(url_for('cart.view_cart'))
