from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User, load_user
from app.utils import load_data, save_data, init_database, validate_token, mark_token_as_used, get_available_roles
import uuid
from datetime import datetime
from config import Config

app_config = Config()
auth_bp = Blueprint('auth', __name__)

# Страница регистрации
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Только администратор может регистрировать новых пользователей
    if current_user.is_authenticated and current_user.role != 'admin':
        flash('Только администратор может регистрировать новых пользователей')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        name = request.form['name'].strip()
        token = request.form['token'].strip()
        
        # Проверка токена
        token_info = validate_token(token)
        if not token_info:
            flash('Неверный или использованный токен')
            return render_template('register.html', roles=get_available_roles())
        
        # Проверка на существование пользователя с таким именем
        users = load_data(app_config.USERS_DB)
        if any(user['username'] == username for user in users):
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html', roles=get_available_roles())
        
        # Создание нового пользователя с токеном для отображения
        display_token = str(uuid.uuid4())[:8].upper()
        new_user = {
            "id": str(uuid.uuid4())[:8],
            "username": username,
            "password": generate_password_hash(password),
            "name": name,
            "role": token_info['role'],
            "token": display_token,
            "projects": []
        }
        
        # Добавление пользователя в базу
        users.append(new_user)
        save_data(app_config.USERS_DB, users)
        
        # Если это исполнитель, добавляем его в команду проекта
        if token_info['role'] == 'worker' and token_info['project_id']:
            projects = load_data(app_config.PROJECTS_DB)
            for project in projects:
                if project['id'] == token_info['project_id']:
                    team = project.get('team', [])
                    if new_user['id'] not in team:
                        team.append(new_user['id'])
                        project['team'] = team
                    break
            save_data(app_config.PROJECTS_DB', projects)
        
        # Отмечаем токен как использованный
        mark_token_as_used(token)
        
        flash('Пользователь успешно зарегистрирован')
        
        # Если пользователь уже авторизован (админ), возвращаем его в панель управления
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        else:
            # Иначе перенаправляем на страницу входа
            return redirect(url_for('auth.login'))

    return render_template('register.html', roles=get_available_roles())


# Страница входа
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_data(app_config.USERS_DB)
        
        if not users:
            flash('База данных пользователей пуста. Обратитесь к администратору.')
            return render_template('login.html')
        
        # Поиск пользователя
        user = None
        for u in users:
            if u['username'] == username:
                user = u
                break
        
        # Отладочная информация (только в режиме разработки)
        from app import app
        if app.debug:
            print(f"Поиск пользователя: {username}")
            print(f"Найдено пользователей: {len(users)}")
            if user:
                # Используем метод get() для безопасного доступа к полям
                name = user.get('name', 'Имя не указано')
                role = user.get('role', 'Роль не указана')
                print(f"Пользователь найден: {name}, роль: {role}")
                # Проверяем пароль и выводим результат
                password_check = check_password_hash(user['password'], password)
                print(f"Проверка пароля: {'успешно' if password_check else 'неудачно'}")
        
        # Проверка пароля
        if user and check_password_hash(user['password'], password):
            # Добавляем проверку наличия необходимых полей
            user_id = user.get('id', str(uuid.uuid4())[:8])
            username = user.get('username', 'unknown')
            name = user.get('name', username)
            role = user.get('role', 'user')
            token = user.get('token')
            
            user_obj = User(user_id, username, name, role, token)
            login_user(user_obj)
            flash(f'Добро пожаловать, {name}!')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль')
            # Дополнительная информация для отладки в режиме разработки
            from app import app
            if app.debug:
                if not user:
                    flash('Пользователь с таким именем не найден', 'debug')
                elif user:
                    flash('Пароль неверный', 'debug')
    
    return render_template('login.html')


# Выход из системы
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# Админ-панель для управления пользователями
@auth_bp.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app_config.USERS_DB)
    return render_template('admin_users.html', users=users)


# Редактирование пользователя
@auth_bp.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app_config.USERS_DB)
    user = next((u for u in users if u['id'] == user_id), None)
    
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('auth.admin_users'))
    
    if request.method == 'POST':
        user['name'] = request.form['name'].strip()
        user['role'] = request.form['role']
        
        if request.form['password']:
            user['password'] = generate_password_hash(request.form['password'])
        
        # Обновляем данные в файле
        for i, u in enumerate(users):
            if u['id'] == user_id:
                users[i] = user
                break
        
        save_data(app_config.USERS_DB', users)
        flash('Пользователь успешно обновлен')
        return redirect(url_for('auth.admin_users'))
    
    return render_template('edit_user.html', user=user, roles=get_available_roles())


# Удаление пользователя
@auth_bp.route('/admin/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app_config.USERS_DB)
    
    # Проверяем, что пользователь существует и это не текущий пользователь
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('auth.admin_users'))
    
    if user_id == current_user.id:
        flash('Нельзя удалить самого себя')
        return redirect(url_for('auth.admin_users'))
    
    # Удаляем пользователя
    users = [u for u in users if u['id'] != user_id]
    save_data(app_config.USERS_DB', users)
    
    flash('Пользователь успешно удален')
    return redirect(url_for('auth.admin_users'))


# ДЛЯ ОТЛАДКИ
@auth_bp.route('/reset-database')
def reset_database():
    from app import app
    if not app.debug:
        flash('Эта функция доступна только в режиме разработки')
        return redirect(url_for('auth.login'))
    
    init_database(force_recreate=True)
    flash('База данных успешно сброшена. Используйте admin/admin для входа.')
    return redirect(url_for('auth.login'))