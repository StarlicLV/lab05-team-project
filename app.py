import os

from flask import Flask, render_template

import models
from api import register_api
from routes import register_blueprints

app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.root_path, 'db.sqlite')
# Потрібен для session (кошик) і flash-повідомлень. Для навчального проєкту достатньо, для реального — зберігати в секреті.
app.config['SECRET_KEY'] = 'dev-secret-key-change-me'

# Закриваємо з’єднання з БД після кожного запиту
app.teardown_appcontext(models.close_db)

# Підключаємо маршрути з папки routes/
register_blueprints(app)

# REST API (/api/v1, /api/v2) та JSON-обробники помилок для них
register_api(app)

# Створюємо таблиці при запуску (безпечно: використовується IF NOT EXISTS)
with app.app_context():
    models.init_db()

# Асортимент кав'ярні: категорії, позиції та ціни (грн).
# Дані зберігаємо тут, а шаблон menu.html виводить їх циклом.
MENU = [
    {
        "id": "coffee",
        "title": "Кава",
        "icon": "☕",
        "items": [
            {"name": "Еспресо", "desc": "Класичний шот зі свіжообсмажених зерен.", "price": 55},
            {"name": "Американо", "desc": "Еспресо з гарячою водою, м'який і легкий.", "price": 60},
            {"name": "Капучино", "desc": "Еспресо з молоком і щільною молочною пінкою.", "price": 75},
            {"name": "Флет-вайт", "desc": "Подвійний еспресо з оксамитовим молоком.", "price": 85},
            {"name": "Фільтр-кава", "desc": "Альтернативне заварювання, яскравий смак зерна.", "price": 80},
        ],
    },
    {
        "id": "desserts",
        "title": "Десерти",
        "icon": "🍰",
        "items": [
            {"name": "Чізкейк", "desc": "Вершковий крем на пісочній основі з ягідним соусом.", "price": 120},
            {"name": "Шоколадний брауні", "desc": "Щільний, з горіхами та темним шоколадом.", "price": 95},
            {"name": "Панна-кота", "desc": "Вершкова, з ваніллю та соусом із сезонних ягід.", "price": 100},
            {"name": "Еклер", "desc": "Заварне тісто з ніжним кремом і глазур'ю.", "price": 70},
            {"name": "Яблучний штрудель", "desc": "Тонке тісто, яблука з корицею, кулька морозива.", "price": 110},
        ],
    },
    {
        "id": "bakery",
        "title": "Випічка",
        "icon": "🥐",
        "items": [
            {"name": "Мигдалевий круасан", "desc": "Хрусткий зовні, з кремом франжипан усередині.", "price": 85},
            {"name": "Круасан з маслом", "desc": "Класичний французький круасан, смачний теплим.", "price": 65},
            {"name": "Булочка з корицею", "desc": "М'яка, з пряною начинкою та вершковою глазур'ю.", "price": 60},
        ],
    },
    {
        "id": "other",
        "title": "Чай та інші напої",
        "icon": "🍵",
        "items": [
            {"name": "Чай (чорний / зелений)", "desc": "Листовий чай, чайничок на двох.", "price": 70},
            {"name": "Какао", "desc": "Густе, на молоці, зі зефірками.", "price": 80},
            {"name": "Лимонад дня", "desc": "Свіжі цитруси та м'ята, подаємо з льодом.", "price": 90},
        ],
    },
]


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/delivery')
def delivery():
    return render_template('delivery.html')


@app.route('/menu')
def menu():
    return render_template('menu.html', categories=MENU)


if __name__ == '__main__':
    # debug=True: автоматичний перезапуск після змін у коді та детальні повідомлення про помилки.
    # Використовується лише під час розробки.
    app.run(debug=True)
