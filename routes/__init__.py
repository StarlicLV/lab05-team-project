"""Усі маршрути розбито на blueprint-и: кожен учасник працює у своєму файлі."""
from .admin import bp as admin_bp
from .cart import bp as cart_bp
from .customers import bp as customers_bp
from .feedback import bp as feedback_bp
from .orders import bp as orders_bp
from .shop import bp as shop_bp


def register_blueprints(app):
    for blueprint in (admin_bp, feedback_bp, cart_bp, shop_bp, orders_bp, customers_bp):
        app.register_blueprint(blueprint)
