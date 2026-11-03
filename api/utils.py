"""Спільні допоміжні функції для всіх endpoint-ів API (v1 і v2).

Їх використовують усі учасники команди, тому тут лише загальні речі:
читання JSON, перевірка полів, пагінація.
"""
import math
import re

from flask import request

from .errors import ApiError


# ---------- Читання тіла запиту ----------

def get_json_body():
    """Повертає тіло запиту як словник або кидає 415 / 400."""
    if not request.is_json:
        raise ApiError(415)
    data = request.get_json(silent=True)   # None, якщо JSON зламаний
    if data is None:
        raise ApiError(400, 'Тіло запиту містить некоректний JSON')
    if not isinstance(data, dict):
        raise ApiError(400, 'Тіло запиту має бути JSON-обʼєктом')
    return data


def raise_if_errors(errors):
    """Якщо словник errors не порожній — відповідь 400 зі списком помилок по полях."""
    if errors:
        raise ApiError(400, 'Помилка валідації даних', errors)


# ---------- Перевірка окремих полів ----------
# Кожна функція додає повідомлення в словник errors (ключ — назва поля)
# і повертає очищене значення (або None, якщо значення некоректне / відсутнє).

def check_string(data, field, errors, required=True, max_len=255):
    value = data.get(field)
    if value is None:
        if required:
            errors[field] = 'Поле обовʼязкове'
        return None
    if not isinstance(value, str):
        errors[field] = 'Має бути рядком'
        return None
    value = value.strip()
    if required and not value:
        errors[field] = 'Поле не може бути порожнім'
        return None
    if len(value) > max_len:
        errors[field] = f'Максимальна довжина — {max_len} символів'
        return None
    return value


def check_number(data, field, errors, required=True, minimum=0):
    value = data.get(field)
    if value is None:
        if required:
            errors[field] = 'Поле обовʼязкове'
        return None
    # bool є підкласом int, тому true/false треба відсікти окремо
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors[field] = 'Має бути числом'
        return None
    if math.isnan(value) or math.isinf(value) or value < minimum:
        errors[field] = f'Має бути числом не менше {minimum}'
        return None
    return value


def normalize_phone(raw):
    """'+38 (050) 111-22-33' -> '+380501112233' (так само, як у routes/orders.py)."""
    return re.sub(r'[\s\-()]', '', raw)


def check_phone(data, field, errors, required=True):
    value = check_string(data, field, errors, required=required, max_len=30)
    if value is None:
        return None
    phone = normalize_phone(value)
    if not re.fullmatch(r'\+?\d{10,13}', phone):
        errors[field] = 'Некоректний номер телефону (10–13 цифр), наприклад +380501112233'
        return None
    return phone


def check_email(data, field, errors):
    """Email необовʼязковий: порожнє значення -> None."""
    value = data.get(field)
    if value is None or value == '':
        return None
    value = check_string(data, field, errors, required=False, max_len=255)
    if value is not None and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
        errors[field] = 'Некоректний email'
        return None
    return value


# ---------- Параметри запиту (?page=1&per_page=10) ----------

def get_int_arg(name, default, minimum=1, maximum=None):
    raw = request.args.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, f'Параметр {name} має бути цілим числом')
    if value < minimum or (maximum is not None and value > maximum):
        limit = f' від {minimum} до {maximum}' if maximum else f' не менше {minimum}'
        raise ApiError(400, f'Параметр {name} має бути{limit}')
    return value


def get_enum_arg(name, allowed, default):
    value = request.args.get(name, default)
    if value not in allowed:
        raise ApiError(400, f'Параметр {name} має бути одним із: {", ".join(allowed)}')
    return value
