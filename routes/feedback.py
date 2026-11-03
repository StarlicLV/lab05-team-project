"""Відгуки: форма для відвідувачів + перегляд і видалення в адмінці (частина А)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from models import execute_db, query_db

bp = Blueprint('feedback', __name__)


def validate_feedback(form):
    """Перевіряє поля форми. Повертає словник помилок {поле: текст}; порожній = усе гаразд."""
    errors = {}
    if not form['name']:
        errors['name'] = 'Вкажіть ім’я.'
    elif len(form['name']) > 100:
        errors['name'] = 'Ім’я не може бути довшим за 100 символів.'

    if not form['email']:
        errors['email'] = 'Вкажіть email.'
    elif '@' not in form['email']:
        errors['email'] = 'Email має містити символ @.'
    elif len(form['email']) > 254:
        errors['email'] = 'Email занадто довгий.'

    if not form['message']:
        errors['message'] = 'Напишіть повідомлення.'
    elif len(form['message']) > 2000:
        errors['message'] = 'Повідомлення не може бути довшим за 2000 символів.'
    return errors


@bp.route('/feedback', methods=['GET', 'POST'])
def feedback_form():
    form = {'name': '', 'email': '', 'message': ''}
    errors = {}

    if request.method == 'POST':
        form = {key: request.form.get(key, '').strip() for key in form}
        errors = validate_feedback(form)
        if not errors:
            # Create: значення підставляємо лише через «?» (захист від SQL-ін’єкцій)
            execute_db('INSERT INTO feedback (name, email, message) VALUES (?, ?, ?)',
                       (form['name'], form['email'], form['message']))
            flash('Дякуємо! Ваш відгук надіслано.')
            # Після успішного POST робимо redirect, щоб оновлення сторінки не надсилало форму вдруге
            return redirect(url_for('feedback.feedback_form'))

    return render_template('feedback.html', form=form, errors=errors)


@bp.route('/admin/feedback')
def admin_list():
    # Read: найновіші відгуки першими
    feedback = query_db('SELECT * FROM feedback ORDER BY created_at DESC, id DESC')
    return render_template('admin/feedback.html', feedback=feedback)


@bp.route('/admin/feedback/<int:feedback_id>/delete', methods=['POST'])
def admin_delete(feedback_id):
    # Delete лише через POST: посилання (GET) може випадково спрацювати, наприклад у пошуковому роботі
    if query_db('SELECT id FROM feedback WHERE id = ?', (feedback_id,), one=True) is None:
        flash('Відгук не знайдено.')
    else:
        execute_db('DELETE FROM feedback WHERE id = ?', (feedback_id,))
        flash('Відгук видалено.')
    return redirect(url_for('feedback.admin_list'))
