"""Документація API: Swagger UI (flasgger) на сторінці /apidocs/.

Якщо пакет flasgger не встановлено, API працює, а на /apidocs/ показується
проста запасна сторінка зі списком endpoints товарів.
Опис кожного endpoint лежить у docstring відповідної функції (формат YAML після ---).
"""
from flask import render_template_string

try:
    from flasgger import Swagger
except ImportError:
    Swagger = None

SWAGGER_TEMPLATE = {
    'swagger': '2.0',
    'info': {
        'title': "API кав'ярні",
        'description': "REST API кав'ярні з десертами: товари, замовлення, клієнти. "
                       'Версія v1 - базова, версія v2 - з пагінацією, сортуванням і розширеними фільтрами.',
        'version': '2.0',
    },
    'tags': [
        {'name': 'Products (v1)', 'description': 'Товари: базові операції CRUD'},
        {'name': 'Products (v2)', 'description': 'Товари: пагінація, сортування, фільтри'},
        {'name': 'Orders (v1)', 'description': 'Замовлення'},
        {'name': 'Customers (v1)', 'description': 'Клієнти: базові операції CRUD'},
        {'name': 'Customers (v2)', 'description': 'Клієнти: пагінація, пошук, сортування'},
    ],
    'definitions': {
        'Product': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer', 'example': 1},
                'name': {'type': 'string', 'example': 'Тірамісу'},
                'description': {'type': 'string', 'example': 'Класичний італійський десерт'},
                'price': {'type': 'number', 'example': 95.0},
                'category': {'type': 'string', 'example': 'Десерти'},
                'is_available': {'type': 'boolean', 'example': True},
            },
        },
        'ProductInput': {
            'type': 'object',
            'required': ['name', 'price', 'category'],
            'properties': {
                'name': {'type': 'string', 'example': 'Лате'},
                'description': {'type': 'string', 'example': 'Кава з молоком'},
                'price': {'type': 'number', 'example': 70},
                'category': {'type': 'string', 'example': 'Кава'},
                'is_available': {'type': 'boolean', 'example': True},
            },
        },
        'Error': {
            'type': 'object',
            'properties': {
                'error': {'type': 'string', 'example': 'Товар не знайдено'},
                'status': {'type': 'integer', 'example': 404},
                'details': {
                    'type': 'object',
                    'description': 'Лише для помилок валідації: поле -> повідомлення',
                    'additionalProperties': {'type': 'string'},
                    'example': {'price': 'Має бути числом не менше 0'},
                },
            },
        },
    },
}


API_DOCS = [
    ('GET', '/api/v1/products', 'Список товарів. Параметри: category, q, available', '200, 400',
     'GET /api/v1/products?category=Кава', '{"count": 1, "products": [{"id": 2, "name": "Лате", "price": 70.0, ...}]}'),
    ('GET', '/api/v1/products/categories', 'Список категорій', '200',
     'GET /api/v1/products/categories', '{"categories": ["Десерти", "Кава"]}'),
    ('GET', '/api/v1/products/<id>', 'Один товар', '200, 404',
     'GET /api/v1/products/1', '{"id": 1, "name": "Тірамісу", "price": 90.0, "category": "Десерти", "is_available": true}'),
    ('POST', '/api/v1/products', 'Створити товар (name, price, category обов\'язкові)', '201, 400',
     '{"name": "Лате", "price": 70, "category": "Кава"}', '201 Created + Location; {"id": 4, "name": "Лате", ...}'),
    ('PUT', '/api/v1/products/<id>', 'Повна заміна товару', '200, 400, 404',
     '{"name": "Лате", "price": 75, "category": "Кава", "is_available": true}', '{"id": 2, "price": 75.0, ...}'),
    ('PATCH', '/api/v1/products/<id>', 'Часткове оновлення (лише передані поля)', '200, 400, 404',
     '{"price": 99.5, "is_available": false}', '{"id": 2, "price": 99.5, "is_available": false, ...}'),
    ('DELETE', '/api/v1/products/<id>', 'Видалити товар (409, якщо він є в замовленнях)', '204, 404, 409',
     'DELETE /api/v1/products/3', '204 No Content (без тіла)'),
    ('GET', '/api/v2/products', 'Список із пагінацією: page, per_page, sort (-price), q, category, min_price, max_price, available', '200, 400',
     'GET /api/v2/products?page=1&per_page=5&sort=-price', '{"data": [...], "meta": {"page": 1, "per_page": 5, "total": 12, "pages": 3}}'),
    ('GET', '/api/v2/products/<id>', 'Один товар (формат v2)', '200, 404',
     'GET /api/v2/products/1', '{"data": {"id": 1, "name": "Тірамісу", ...}}'),
]

DOCS_TEMPLATE = r"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Документація API товарів</title>
<style>
 :root { --bg:#fff; --fg:#1f2937; --card:#f3f4f6; --line:#d1d5db; --accent:#b45309; }
 @media (prefers-color-scheme: dark) { :root { --bg:#111827; --fg:#e5e7eb; --card:#1f2937; --line:#374151; --accent:#fbbf24; } }
 body { background:var(--bg); color:var(--fg); font-family:system-ui,sans-serif; margin:0; padding:16px; max-width:900px; margin:auto; }
 .ep { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; margin:12px 0; }
 .m { font-weight:700; color:var(--accent); } code,pre { word-break:break-all; white-space:pre-wrap; }
 h1 { font-size:1.5rem; } small { opacity:.8; }
</style></head><body>
<h1>API товарів кав'ярні</h1>
<p>Формат даних: JSON. Версії: <b>v1</b> (базова) і <b>v2</b> (пагінація, сортування, фільтри).
Помилки повертаються як <code>{"error": "...", "status": 400, "details": [...]}</code>.</p>
{% for m, url, desc, codes, req, resp in docs %}
<div class="ep">
  <div><span class="m">{{ m }}</span> <code>{{ url }}</code></div>
  <div>{{ desc }}</div>
  <small>Коди відповідей: {{ codes }}</small>
  <div><small>Запит:</small><pre>{{ req }}</pre></div>
  <div><small>Відповідь:</small><pre>{{ resp }}</pre></div>
</div>
{% endfor %}
</body></html>
"""


def init_docs(app):
    """Підключає /apidocs/ (Swagger UI або запасну сторінку)."""
    if Swagger is not None:
        Swagger(app, template=SWAGGER_TEMPLATE)
    else:
        app.add_url_rule('/apidocs/', 'api_docs_fallback',
                         lambda: render_template_string(DOCS_TEMPLATE, docs=API_DOCS))
