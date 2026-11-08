"""Автотести REST API кав'ярні (лабораторна робота 05).

Запуск з кореня проєкту:
    python -m unittest discover -s tests -v

Кожен тест працює з власною тимчасовою базою SQLite (з тестовими даними зі schema.sql та models.SEED_*),
тому реальний db.sqlite не змінюється, а тести не залежать один від одного.
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from flask import Flask  # noqa: E402

import models  # noqa: E402
from api import register_api  # noqa: E402


def make_app(db_path):
    app = Flask('coffee_test', root_path=ROOT)   # root_path потрібен, щоб знайти schema.sql
    app.config.update(DATABASE=db_path, TESTING=True)
    app.teardown_appcontext(models.close_db)
    register_api(app)
    with app.app_context():
        models.init_db()
    return app


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        self.app = make_app(self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    # --- допоміжні методи ---
    def create_order(self, **overrides):
        body = {'customer_id': 1, 'address': 'Луцьк, вул. Лесі Українки 1',
                'items': [{'product_id': 4, 'quantity': 2}]}
        body.update(overrides)
        return self.client.post('/api/v1/orders', json=body)

    def assert_error(self, response, status, field=None):
        self.assertEqual(response.status_code, status)
        self.assertTrue(response.is_json)
        data = response.get_json()
        self.assertEqual(data['status'], status)
        self.assertIn('error', data)
        if field:
            self.assertIn(field, data.get('details', {}))
        return data


class TestApiRoot(ApiTestCase):
    def test_index_lists_versions(self):
        r = self.client.get('/api')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['versions'], {'v1': '/api/v1', 'v2': '/api/v2'})

    def test_unknown_api_path_returns_json_404(self):
        self.assert_error(self.client.get('/api/v1/nothing'), 404)

    def test_wrong_method_returns_json_405(self):
        self.assert_error(self.client.delete('/api/v1/products'), 405)

    def test_apidocs_page_available(self):
        r = self.client.get('/apidocs/')
        self.assertEqual(r.status_code, 200)


class TestProductsV1(ApiTestCase):
    def test_list_all(self):
        data = self.client.get('/api/v1/products').get_json()
        self.assertEqual(data['count'], 8)
        self.assertEqual(len(data['products']), 8)

    def test_list_filter_category(self):
        data = self.client.get('/api/v1/products?category=Десерти').get_json()
        self.assertEqual(data['count'], 3)
        self.assertTrue(all(p['category'] == 'Десерти' for p in data['products']))

    def test_list_search_q(self):
        data = self.client.get('/api/v1/products?q=круасан').get_json()
        self.assertEqual(data['count'], 1)

    def test_list_available_false_is_empty_by_default(self):
        self.assertEqual(self.client.get('/api/v1/products?available=false').get_json()['count'], 0)

    def test_list_bad_available_param(self):
        self.assert_error(self.client.get('/api/v1/products?available=maybe'), 400)

    def test_categories(self):
        cats = self.client.get('/api/v1/products/categories').get_json()['categories']
        self.assertIn('Кава', cats)
        self.assertIn('Десерти', cats)

    def test_get_one(self):
        r = self.client.get('/api/v1/products/1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['name'], 'Еспресо')
        self.assertIs(r.get_json()['is_available'], True)

    def test_get_one_not_found(self):
        self.assert_error(self.client.get('/api/v1/products/99999'), 404)

    def test_create(self):
        r = self.client.post('/api/v1/products', json={'name': 'Лате', 'price': 70, 'category': 'Кава'})
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body['name'], 'Лате')
        self.assertEqual(body['price'], 70.0)
        self.assertTrue(r.headers['Location'].endswith('/api/v1/products/%d' % body['id']))
        self.assertEqual(self.client.get('/api/v1/products/%d' % body['id']).status_code, 200)

    def test_create_missing_fields(self):
        data = self.assert_error(self.client.post('/api/v1/products', json={}), 400, 'name')
        self.assertIn('price', data['details'])
        self.assertIn('category', data['details'])

    def test_create_negative_price(self):
        self.assert_error(self.client.post('/api/v1/products',
                          json={'name': 'X', 'price': -1, 'category': 'Кава'}), 400, 'price')

    def test_create_price_as_string_and_bool(self):
        for bad in ('70', True):
            r = self.client.post('/api/v1/products', json={'name': 'X', 'price': bad, 'category': 'Кава'})
            self.assert_error(r, 400, 'price')

    def test_create_name_too_long(self):
        self.assert_error(self.client.post('/api/v1/products',
                          json={'name': 'a' * 101, 'price': 1, 'category': 'Кава'}), 400, 'name')

    def test_create_not_json_is_415(self):
        self.assert_error(self.client.post('/api/v1/products', data='name=Лате'), 415)

    def test_create_broken_json_is_400(self):
        r = self.client.post('/api/v1/products', data='{"name": ', content_type='application/json')
        self.assert_error(r, 400)

    def test_create_json_array_is_400(self):
        self.assert_error(self.client.post('/api/v1/products', json=[1, 2]), 400)

    def test_put_replace(self):
        r = self.client.put('/api/v1/products/1', json={'name': 'Еспресо new', 'price': 50, 'category': 'Кава'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['name'], 'Еспресо new')

    def test_put_requires_all_fields(self):
        self.assert_error(self.client.put('/api/v1/products/1', json={'price': 50}), 400, 'name')

    def test_put_not_found(self):
        r = self.client.put('/api/v1/products/9999', json={'name': 'a', 'price': 1, 'category': 'b'})
        self.assert_error(r, 404)

    def test_patch_changes_only_given_fields(self):
        before = self.client.get('/api/v1/products/1').get_json()
        r = self.client.patch('/api/v1/products/1', json={'price': 99.5, 'is_available': False})
        self.assertEqual(r.status_code, 200)
        after = r.get_json()
        self.assertEqual(after['price'], 99.5)
        self.assertIs(after['is_available'], False)
        self.assertEqual(after['name'], before['name'])

    def test_patch_empty_body(self):
        self.assert_error(self.client.patch('/api/v1/products/1', json={}), 400)

    def test_patch_invalid_is_available(self):
        self.assert_error(self.client.patch('/api/v1/products/1', json={'is_available': 'yes'}), 400, 'is_available')

    def test_patch_not_found(self):
        self.assert_error(self.client.patch('/api/v1/products/9999', json={'price': 1}), 404)

    def test_delete(self):
        self.assertEqual(self.client.delete('/api/v1/products/8').status_code, 204)
        self.assert_error(self.client.get('/api/v1/products/8'), 404)

    def test_delete_not_found(self):
        self.assert_error(self.client.delete('/api/v1/products/9999'), 404)

    def test_delete_product_used_in_order_is_409(self):
        self.assertEqual(self.create_order().status_code, 201)
        self.assert_error(self.client.delete('/api/v1/products/4'), 409)


class TestProductsV2(ApiTestCase):
    def test_pagination_meta(self):
        data = self.client.get('/api/v2/products?page=1&per_page=3').get_json()
        self.assertEqual(len(data['data']), 3)
        self.assertEqual(data['meta'], {'page': 1, 'per_page': 3, 'total': 8, 'pages': 3})

    def test_last_page_has_remainder(self):
        data = self.client.get('/api/v2/products?page=3&per_page=3').get_json()
        self.assertEqual(len(data['data']), 2)

    def test_page_beyond_end_is_empty(self):
        self.assertEqual(self.client.get('/api/v2/products?page=99').get_json()['data'], [])

    def test_sort_desc_by_price(self):
        prices = [p['price'] for p in self.client.get('/api/v2/products?sort=-price').get_json()['data']]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_price_range(self):
        data = self.client.get('/api/v2/products?min_price=70&max_price=80').get_json()
        self.assertTrue(data['data'])
        self.assertTrue(all(70 <= p['price'] <= 80 for p in data['data']))

    def test_invalid_params(self):
        for query in ('page=0', 'page=abc', 'per_page=101', 'sort=hack', 'min_price=abc', 'available=x'):
            with self.subTest(query=query):
                self.assert_error(self.client.get('/api/v2/products?' + query), 400)

    def test_sql_injection_in_sort_is_rejected(self):
        self.assert_error(self.client.get('/api/v2/products?sort=id;DROP TABLE products'), 400)
        self.assertEqual(self.client.get('/api/v1/products').get_json()['count'], 8)

    def test_get_one_is_wrapped_in_data(self):
        self.assertEqual(self.client.get('/api/v2/products/1').get_json()['data']['id'], 1)

    def test_get_one_not_found(self):
        self.assert_error(self.client.get('/api/v2/products/9999'), 404)


class TestCustomersV1(ApiTestCase):
    NEW = {'name': 'Марія Шевченко', 'phone': '+380931112233', 'email': 'maria@example.com'}

    def test_list(self):
        customers = self.client.get('/api/v1/customers').get_json()['customers']
        self.assertEqual(len(customers), 2)
        self.assertIn('orders_count', customers[0])

    def test_get_one_and_404(self):
        self.assertEqual(self.client.get('/api/v1/customers/1').get_json()['name'], 'Олена Коваль')
        self.assert_error(self.client.get('/api/v1/customers/9999'), 404)

    def test_customer_orders(self):
        self.create_order()
        data = self.client.get('/api/v1/customers/1/orders').get_json()
        self.assertEqual(data['customer_id'], 1)
        self.assertEqual(len(data['orders']), 1)
        self.assert_error(self.client.get('/api/v1/customers/9999/orders'), 404)

    def test_create(self):
        r = self.client.post('/api/v1/customers', json=self.NEW)
        self.assertEqual(r.status_code, 201)
        self.assertIn('/api/v1/customers/', r.headers['Location'])
        self.assertEqual(r.get_json()['orders_count'], 0)

    def test_create_normalizes_phone(self):
        r = self.client.post('/api/v1/customers',
                             json={'name': 'Тест', 'phone': '+38 (093) 111-22-44'})
        self.assertEqual(r.get_json()['phone'], '+380931112244')

    def test_create_duplicate_phone_is_409(self):
        self.assert_error(self.client.post('/api/v1/customers',
                          json={'name': 'Дубль', 'phone': '+380501112233'}), 409)

    def test_create_validation(self):
        data = self.assert_error(self.client.post('/api/v1/customers',
                                 json={'name': '', 'phone': '123', 'email': 'bad'}), 400, 'name')
        self.assertIn('phone', data['details'])
        self.assertIn('email', data['details'])

    def test_create_not_json_is_415(self):
        self.assert_error(self.client.post('/api/v1/customers', data='x'), 415)

    def test_put_replace(self):
        r = self.client.put('/api/v1/customers/2', json=self.NEW)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['phone'], '+380931112233')

    def test_put_phone_of_another_customer_is_409(self):
        self.assert_error(self.client.put('/api/v1/customers/2',
                          json={'name': 'X', 'phone': '+380501112233'}), 409)

    def test_patch_name_only(self):
        r = self.client.patch('/api/v1/customers/1', json={'name': 'Нове імʼя'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['name'], 'Нове імʼя')
        self.assertEqual(r.get_json()['phone'], '+380501112233')

    def test_patch_not_found(self):
        self.assert_error(self.client.patch('/api/v1/customers/9999', json={'name': 'X'}), 404)

    def test_delete_without_orders(self):
        self.assertEqual(self.client.delete('/api/v1/customers/2').status_code, 204)
        self.assert_error(self.client.get('/api/v1/customers/2'), 404)

    def test_delete_with_orders_is_409(self):
        self.create_order()
        self.assert_error(self.client.delete('/api/v1/customers/1'), 409)

    def test_delete_not_found(self):
        self.assert_error(self.client.delete('/api/v1/customers/9999'), 404)


class TestCustomersV2(ApiTestCase):
    def test_list_has_meta(self):
        data = self.client.get('/api/v2/customers').get_json()
        self.assertEqual(data['meta']['total'], 2)
        self.assertEqual(len(data['data']), 2)

    def test_search(self):
        data = self.client.get('/api/v2/customers?q=Олена').get_json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['name'], 'Олена Коваль')

    def test_sort_by_name(self):
        names = [c['name'] for c in self.client.get('/api/v2/customers?sort=name&order=asc').get_json()['data']]
        self.assertEqual(names, sorted(names))

    def test_invalid_params(self):
        for query in ('sort=phone', 'order=up', 'per_page=0', 'page=x'):
            with self.subTest(query=query):
                self.assert_error(self.client.get('/api/v2/customers?' + query), 400)

    def test_detail_total_spent_ignores_cancelled(self):
        first = self.create_order().get_json()      # 2 x 95 = 190
        second = self.create_order().get_json()
        self.client.patch('/api/v1/orders/%d/status' % second['id'], json={'status': 'cancelled'})
        data = self.client.get('/api/v2/customers/1').get_json()
        self.assertEqual(len(data['orders']), 2)
        self.assertEqual(data['total_spent'], first['total'])

    def test_detail_not_found(self):
        self.assert_error(self.client.get('/api/v2/customers/9999'), 404)


class TestOrdersV1(ApiTestCase):
    def test_list_empty(self):
        self.assertEqual(self.client.get('/api/v1/orders').get_json(), {'count': 0, 'orders': []})

    def test_create_without_promo(self):
        r = self.create_order()
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertEqual(body['status'], 'new')
        self.assertEqual(body['total'], 190.0)
        self.assertEqual(body['discount'], 0)
        self.assertEqual(body['items'][0]['line_total'], 190.0)
        self.assertTrue(r.headers['Location'].endswith('/api/v1/orders/%d' % body['id']))

    def test_create_with_promo_sweet10(self):
        body = self.create_order(promo_code='sweet10').get_json()   # регістр не важливий
        self.assertEqual(body['promo_code'], 'SWEET10')
        self.assertEqual(body['discount'], 19.0)
        self.assertEqual(body['total'], 171.0)

    def test_duplicate_items_are_merged(self):
        body = self.create_order(items=[{'product_id': 1, 'quantity': 1},
                                        {'product_id': 1, 'quantity': 2}]).get_json()
        self.assertEqual(len(body['items']), 1)
        self.assertEqual(body['items'][0]['quantity'], 3)

    def test_price_is_taken_from_db_not_from_request(self):
        body = self.create_order(items=[{'product_id': 1, 'quantity': 1, 'price': 0.01}]).get_json()
        self.assertEqual(body['items'][0]['price_at_order'], 45.0)

    def test_create_missing_fields(self):
        data = self.assert_error(self.client.post('/api/v1/orders', json={}), 400, 'customer_id')
        for field in ('address', 'items'):
            self.assertIn(field, data['details'])

    def test_create_bad_items(self):
        for items in ([], 'x', [1], [{'product_id': 1, 'quantity': 0}], [{'product_id': 'a', 'quantity': 1}]):
            with self.subTest(items=items):
                self.assert_error(self.create_order(items=items), 400)

    def test_create_unknown_customer(self):
        self.assert_error(self.create_order(customer_id=9999), 404)

    def test_create_unknown_product(self):
        self.assert_error(self.create_order(items=[{'product_id': 9999, 'quantity': 1}]), 404)

    def test_create_unavailable_product(self):
        self.client.patch('/api/v1/products/4', json={'is_available': False})
        self.assert_error(self.create_order(), 400, 'items')

    def test_create_invalid_promo(self):
        self.assert_error(self.create_order(promo_code='NOPE'), 400, 'promo_code')

    def test_failed_order_is_not_saved(self):
        self.create_order(promo_code='NOPE')
        self.assertEqual(self.client.get('/api/v1/orders').get_json()['count'], 0)

    def test_create_not_json_is_415(self):
        self.assert_error(self.client.post('/api/v1/orders', data='x'), 415)

    def test_get_one(self):
        order_id = self.create_order().get_json()['id']
        r = self.client.get('/api/v1/orders/%d' % order_id)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['customer_name'], 'Олена Коваль')

    def test_get_one_not_found(self):
        self.assert_error(self.client.get('/api/v1/orders/99999'), 404)

    def test_filter_by_status(self):
        order_id = self.create_order().get_json()['id']
        self.create_order()
        self.client.patch('/api/v1/orders/%d/status' % order_id, json={'status': 'done'})
        self.assertEqual(self.client.get('/api/v1/orders?status=done').get_json()['count'], 1)
        self.assertEqual(self.client.get('/api/v1/orders?status=new').get_json()['count'], 1)

    def test_filter_by_unknown_status(self):
        self.assert_error(self.client.get('/api/v1/orders?status=zzz'), 400)

    def test_change_status(self):
        order_id = self.create_order().get_json()['id']
        r = self.client.patch('/api/v1/orders/%d/status' % order_id, json={'status': 'preparing'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['status'], 'preparing')

    def test_change_status_invalid(self):
        order_id = self.create_order().get_json()['id']
        for bad in ('zzz', 5, None):
            with self.subTest(status=bad):
                self.assert_error(self.client.patch('/api/v1/orders/%d/status' % order_id,
                                                    json={'status': bad}), 400, 'status')

    def test_change_status_not_found(self):
        self.assert_error(self.client.patch('/api/v1/orders/9999/status', json={'status': 'done'}), 404)


class TestHugeNumbers(ApiTestCase):
    """Дуже великі цілі числа (> 2**63) SQLite не приймає (OverflowError).
    Раніше API повертало 500; після виправлення в api/errors.py має бути 400."""
    BIG = 10 ** 30

    def test_huge_id_in_url_returns_400(self):
        self.assert_error(self.client.get('/api/v1/products/%d' % self.BIG), 400)

    def test_huge_ids_in_order_return_400(self):
        self.assert_error(self.create_order(items=[{'product_id': self.BIG, 'quantity': 1}]), 400)
        self.assert_error(self.create_order(customer_id=self.BIG), 400)

    def test_huge_page_number_returns_400(self):
        self.assert_error(self.client.get('/api/v2/products?page=%d' % self.BIG), 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
