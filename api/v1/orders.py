"""API v1: замовлення та промокоди (відповідальний: Мельник Віталій, routes/orders.py з лабораторної 4).

TODO (4 endpoints, префікс /api/v1/orders):
    GET     /              список замовлень (необовʼязковий фільтр ?status=, статуси: models.ORDER_STATUSES)
    GET     /<id>          замовлення з позиціями (JOIN order_items + products); 404, якщо немає
    POST    /              створити замовлення з JSON: customer_id, address, items: [{product_id, quantity}]
    PATCH   /<id>/status   змінити статус (перевіряти за models.ORDER_STATUSES; 400 при невідомому статусі)

Підказки:
    * total рахуйте як сума price * quantity, у order_items зберігайте price_at_order (див. create_order у routes/orders.py);
    * створення замовлення й позицій робіть в одній транзакції (один commit);
    * quantity: ціле число > 0; неіснуючий customer_id / product_id -> 404 або 400 з поясненням у details;
    * недоступний товар (is_available = 0) замовити не можна -> 400;
    * список замовлень клієнта вже зроблено в api/v1/customers.py (/customers/<id>/orders).
Допоміжні функції та приклад оформлення: api/utils.py, api/v1/customers.py.
"""
from flask import Blueprint

bp = Blueprint('v1_orders', __name__, url_prefix='/orders')
