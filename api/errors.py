"""Єдиний формат помилок REST API.

Усі помилки на адресах /api/... повертаються у JSON:
    {"error": "Опис помилки", "status": 404, "details": {...}}
Поле details є лише для помилок валідації (поле -> повідомлення).
Звичайні HTML-сторінки сайту (/menu, /cart, ...) обробляються як і раніше.
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

# Українські повідомлення для типових HTTP-помилок
DEFAULT_MESSAGES = {
    400: 'Некоректний запит',
    404: 'Ресурс не знайдено',
    405: 'Метод не дозволений для цієї адреси',
    409: 'Конфлікт даних',
    415: 'Тіло запиту має бути у форматі JSON (Content-Type: application/json)',
    500: 'Внутрішня помилка сервера',
}


class ApiError(Exception):
    """Помилка, яку можна викликати з будь-якого endpoint: raise ApiError(404, 'Клієнта не знайдено')."""

    def __init__(self, status, message=None, details=None):
        super().__init__(message)
        self.status = status
        self.message = message or DEFAULT_MESSAGES.get(status, 'Помилка')
        self.details = details


def error_response(status, message, details=None):
    body = {'error': message, 'status': status}
    if details:
        body['details'] = details
    return jsonify(body), status


def _is_api_request():
    return request.path == '/api' or request.path.startswith('/api/')


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(error.status, error.message, error.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        # Для сторінок сайту лишаємо стандартну поведінку Flask (HTML)
        if not _is_api_request():
            return error
        message = DEFAULT_MESSAGES.get(error.code, error.description)
        return error_response(error.code, message)

    @app.errorhandler(OverflowError)
    def handle_overflow(error):
        # Надто велике число (наприклад, id з 30 цифр) SQLite не приймає: це помилка клієнта, а не сервера
        if not _is_api_request():
            raise error
        return error_response(400, 'Числове значення виходить за допустимі межі')

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if not _is_api_request():
            raise error
        app.logger.exception('Необроблена помилка в API')
        return error_response(500, DEFAULT_MESSAGES[500])
