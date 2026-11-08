# Звіт про тестування REST API кав'ярні (lab05)

Автор розділу: Кубський Максим Сергійович (частина «Тести та документація»). Група ІПЗ-21.

## 1. Що і як тестувалось

| Рівень | Інструмент | Де лежить | Що перевіряє |
|---|---|---|---|
| Автоматичні тести | `unittest` (стандартна бібліотека) + `app.test_client()` | `tests/test_api.py` | усі endpoints v1 і v2: успішні сценарії, валідація, коди 400/404/405/409/415, формат JSON-помилок |
| Ручні/сквозні сценарії | Postman (Collection Runner) | `postman_collection.json` | повний ланцюжок на живому сервері: створення → читання → зміна → видалення, змінні `product_id`, `customer_id`, `order_id` |
| Окремі сценарії замовлень | Postman | `postman_orders.json` | колекція автора модуля замовлень (11 запитів) |

Кожен автотест працює з **власною тимчасовою базою SQLite** (тестові товари, клієнти й промокоди зі `schema.sql`/`models.py`), тому реальний `db.sqlite` не змінюється, а тести не залежать один від одного.

## 2. Автоматичні тести (unittest)

Запуск з кореня проєкту: `python -m unittest discover -s tests -v`

| Група тестів | Кількість |
|---|---|
| Загальне (/api, 404, 405, /apidocs/) | 4 |
| Товари v1 | 26 |
| Товари v2 | 9 |
| Клієнти v1 | 15 |
| Клієнти v2 | 6 |
| Замовлення v1 | 20 |
| Дуже великі числа (регресія виправленої помилки) | 3 |
| **Разом** | **83** |

**Результат останнього запуску:** `Ran 83 tests ... OK` — усі тести пройдено.

## 3. Сценарії Postman (`postman_collection.json`)

Колекція містить **63 запити** у 7 папках. До кожного запиту додано скрипт `pm.test`: перевіряється код відповіді, формат JSON і ключові поля відповіді; запити, що створюють ресурси, зберігають `id` у змінних колекції для наступних кроків. Для кожного endpoint є і успішний запит, і щонайменше один запит з помилкою (неіснуючий id, порожнє поле, невалідний параметр тощо).

### 0. Загальне

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 1 | GET /api — перелік версій<br>`GET /api` | 200 | versions.v1 = /api/v1; versions.v2 = /api/v2 |
| 2 | GET неіснуюча адреса — JSON 404<br>`GET /api/v1/nothing` | 404 | status = 404; error є рядком |
| 3 | DELETE /products — метод не дозволений (405)<br>`DELETE /api/v1/products` | 405 | status = 405 |

### 1. Товари v1

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 4 | GET список товарів<br>`GET /api/v1/products` | 200 | count ≥ 1; products є масивом |
| 5 | GET список: фільтр category=Кава<br>`GET /api/v1/products?category=Кава` | 200 | count ≥ 1 |
| 6 | GET список: available=maybe — помилка 400<br>`GET /api/v1/products?available=maybe` | 400 | status = 400 |
| 7 | GET категорії<br>`GET /api/v1/products/categories` | 200 | categories є масивом |
| 8 | POST створити товар<br>`POST /api/v1/products` | 201 | name = Тестове лате; price = 70; is_available = True |
| 9 | POST без обовʼязкових полів — помилка 400<br>`POST /api/v1/products` | 400 | details.name є рядком; details.price є рядком; details.category є рядком |
| 10 | POST від’ємна ціна — помилка 400<br>`POST /api/v1/products` | 400 | details.price є рядком |
| 11 | POST не JSON — помилка 415<br>`POST /api/v1/products` | 415 | status = 415 |
| 12 | GET товар за id<br>`GET /api/v1/products/{{product_id}}` | 200 | id = product_id; name = Тестове лате |
| 13 | GET неіснуючий товар — 404<br>`GET /api/v1/products/99999` | 404 | error є рядком |
| 14 | PUT повна заміна товару<br>`PUT /api/v1/products/{{product_id}}` | 200 | price = 100; name = Тестове лате (оновл.) |
| 15 | PUT без полів — помилка 400<br>`PUT /api/v1/products/{{product_id}}` | 400 | details.name є рядком |
| 16 | PUT неіснуючий товар — 404<br>`PUT /api/v1/products/99999` | 404 | — |
| 17 | PATCH змінити лише опис<br>`PATCH /api/v1/products/{{product_id}}` | 200 | description = Лише опис змінено; price = 100 |
| 18 | PATCH порожнє тіло — помилка 400<br>`PATCH /api/v1/products/{{product_id}}` | 400 | — |
| 19 | POST тимчасовий товар для видалення<br>`POST /api/v1/products` | 201 | — |
| 20 | DELETE тимчасовий товар<br>`DELETE /api/v1/products/{{tmp_product_id}}` | 204 | — |
| 21 | GET видалений товар — 404<br>`GET /api/v1/products/{{tmp_product_id}}` | 404 | — |
| 22 | DELETE повторно — 404<br>`DELETE /api/v1/products/{{tmp_product_id}}` | 404 | — |

### 2. Товари v2

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 23 | GET список з пагінацією<br>`GET /api/v2/products?page=1&per_page=3` | 200 | meta.page = 1; meta.per_page = 3; meta.total ≥ 1; data є масивом |
| 24 | GET сортування -price<br>`GET /api/v2/products?sort=-price&per_page=5` | 200 | data є масивом |
| 25 | GET фільтр цін min_price/max_price<br>`GET /api/v2/products?min_price=50&max_price=120` | 200 | data є масивом |
| 26 | GET per_page=101 — помилка 400<br>`GET /api/v2/products?per_page=101` | 400 | status = 400 |
| 27 | GET sort=hack — помилка 400<br>`GET /api/v2/products?sort=hack` | 400 | status = 400 |
| 28 | GET товар за id (формат v2)<br>`GET /api/v2/products/{{product_id}}` | 200 | data.id = product_id |
| 29 | GET неіснуючий товар v2 — 404<br>`GET /api/v2/products/99999` | 404 | — |

### 3. Клієнти v1

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 30 | POST створити клієнта<br>`POST /api/v1/customers` | 201 | name = Тестовий Клієнт; orders_count = 0 |
| 31 | POST дубль телефону — 409<br>`POST /api/v1/customers` | 409 | status = 409 |
| 32 | POST некоректні дані — 400<br>`POST /api/v1/customers` | 400 | details.name є рядком; details.phone є рядком; details.email є рядком |
| 33 | GET список клієнтів<br>`GET /api/v1/customers` | 200 | customers є масивом |
| 34 | GET клієнт за id<br>`GET /api/v1/customers/{{customer_id}}` | 200 | id = customer_id |
| 35 | GET неіснуючий клієнт — 404<br>`GET /api/v1/customers/99999` | 404 | — |
| 36 | PATCH змінити імʼя<br>`PATCH /api/v1/customers/{{customer_id}}` | 200 | name = Тестовий Клієнт (PATCH) |
| 37 | PUT повна заміна клієнта<br>`PUT /api/v1/customers/{{customer_id}}` | 200 | email = new@example.com |
| 38 | GET замовлення клієнта<br>`GET /api/v1/customers/{{customer_id}}/orders` | 200 | orders є масивом |
| 39 | POST тимчасовий клієнт<br>`POST /api/v1/customers` | 201 | — |
| 40 | DELETE тимчасовий клієнт<br>`DELETE /api/v1/customers/{{tmp_customer_id}}` | 204 | — |
| 41 | DELETE повторно — 404<br>`DELETE /api/v1/customers/{{tmp_customer_id}}` | 404 | — |

### 4. Замовлення v1

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 42 | POST створити замовлення<br>`POST /api/v1/orders` | 201 | status = new; total = 200; discount = 0 |
| 43 | POST із промокодом SWEET10 (знижка 10%)<br>`POST /api/v1/orders` | 201 | promo_code = SWEET10; discount = 20; total = 180 |
| 44 | POST без обовʼязкових полів — 400<br>`POST /api/v1/orders` | 400 | details.customer_id є рядком; details.address є рядком; details.items є рядком |
| 45 | POST неіснуючий клієнт — 404<br>`POST /api/v1/orders` | 404 | — |
| 46 | POST неіснуючий товар — 404<br>`POST /api/v1/orders` | 404 | — |
| 47 | POST недійсний промокод — 400<br>`POST /api/v1/orders` | 400 | details.promo_code є рядком |
| 48 | POST quantity = 0 — 400<br>`POST /api/v1/orders` | 400 | — |
| 49 | GET список замовлень<br>`GET /api/v1/orders` | 200 | count ≥ 2; orders є масивом |
| 50 | GET список: ?status=new<br>`GET /api/v1/orders?status=new` | 200 | count ≥ 1 |
| 51 | GET список: ?status=zzz — помилка 400<br>`GET /api/v1/orders?status=zzz` | 400 | — |
| 52 | GET замовлення за id<br>`GET /api/v1/orders/{{order_id}}` | 200 | id = order_id; items є масивом |
| 53 | GET неіснуюче замовлення — 404<br>`GET /api/v1/orders/99999` | 404 | — |
| 54 | PATCH змінити статус на preparing<br>`PATCH /api/v1/orders/{{order_id}}/status` | 200 | status = preparing |
| 55 | PATCH невідомий статус — 400<br>`PATCH /api/v1/orders/{{order_id}}/status` | 400 | details.status є рядком |

### 5. Клієнти v2

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 56 | GET список з пагінацією<br>`GET /api/v2/customers?page=1&per_page=5` | 200 | meta.page = 1; meta.total ≥ 1; data є масивом |
| 57 | GET пошук q=Тестовий<br>`GET /api/v2/customers?q=Тестовий` | 200 | meta.total ≥ 1 |
| 58 | GET сортування за імʼям<br>`GET /api/v2/customers?sort=name&order=asc` | 200 | data є масивом |
| 59 | GET sort=phone — помилка 400<br>`GET /api/v2/customers?sort=phone` | 400 | — |
| 60 | GET клієнт із замовленнями і total_spent<br>`GET /api/v2/customers/{{customer_id}}` | 200 | orders є масивом; total_spent ≥ 1; orders_count ≥ 2 |
| 61 | GET неіснуючий клієнт v2 — 404<br>`GET /api/v2/customers/99999` | 404 | — |

### 6. Конфлікти цілісності (409)

| № | Запит | Очікуваний код | Додаткові перевірки |
|---|---|---|---|
| 62 | DELETE клієнт із замовленнями — 409<br>`DELETE /api/v1/customers/{{customer_id}}` | 409 | status = 409 |
| 63 | DELETE товар, що є в замовленнях — 409<br>`DELETE /api/v1/products/{{product_id}}` | 409 | status = 409 |

**Результат:** усі 63 запитів колекції виконано двічі поспіль на чистій базі (повторний запуск не дає конфліктів, бо телефони клієнтів генеруються унікальними) — розбіжностей з очікуваними кодами і перевірками немає.

> Скріншот Collection Runner (усі тести зелені) додається до README в розділ «Результати тестування».

## 4. Покриття кодів відповідей

| Код | Де перевірено |
|---|---|
| 200 | усі GET, PUT, PATCH |
| 201 | POST товару, клієнта, замовлення (заголовок `Location`) |
| 204 | DELETE товару й клієнта |
| 400 | помилки валідації, некоректні query-параметри, зламаний JSON, невалідний промокод, невідомий статус |
| 404 | неіснуючий товар / клієнт / замовлення / адреса |
| 405 | `DELETE /api/v1/products` |
| 409 | дубль телефону, видалення клієнта із замовленнями, видалення товару, що є в замовленнях |
| 415 | тіло запиту не JSON |
| 500 | не викликається штатними сценаріями |

## 5. Знайдені проблеми

Обидві проблеми знайдено під час тестування і виправлено командою.

**1. Дуже великі цілі числа давали 500 замість 400.** Значення більше `2**63` SQLite не приймає, Python кидає `OverflowError`, і API відповідало `500 Внутрішня помилка сервера`. Відтворення:

```text
GET  /api/v1/products/1000000000000000000000000000000        -> 500 (тепер 400)
GET  /api/v2/products?page=1000000000000000000000000000000   -> 500 (тепер 400)
POST /api/v1/orders  {"customer_id": 1, "address": "a", "items": [{"product_id": 1000000000000000000000000000000, "quantity": 1}]}  -> 500 (тепер 400)
```

Виправлення: обробник `OverflowError` в `api/errors.py` повертає `400`. Тести `TestHugeNumbers` перевіряють, що помилка не повернеться.

**2. `flasgger` не було в `requirements.txt`.** Без нього `/apidocs/` показував запасну сторінку лише з endpoints товарів, а не повний Swagger UI. Пакет додано в `requirements.txt`.
