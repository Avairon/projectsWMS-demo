# Все либы(flask + зависимости)

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import os
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from dateutil.parser import parse as parse_date
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Конфигурация для загрузки файлов
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Создание директории для базы данных, если её нет
os.makedirs(app.config['DATABASE_PATH'], exist_ok=True)
# Создание директории для загрузки файлов, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Допустимые расширения файлов
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

# Инициализация JSON файлов с данными, если их нет
def init_database(force_recreate=False):
    """Инициализация базы данных. Если force_recreate=True, пересоздает файлы даже если они существуют"""
    
    # Если нужно принудительно пересоздать базу данных
    if force_recreate:
        print("Принудительное пересоздание базы данных...")
        if os.path.exists(app.config['USERS_DB']):
            os.remove(app.config['USERS_DB'])
        if os.path.exists(app.config['PROJECTS_DB']):
            os.remove(app.config['PROJECTS_DB'])
        if os.path.exists(app.config['TASKS_DB']):
            os.remove(app.config['TASKS_DB'])
    
    # Инициализация users.json
    if not os.path.exists(app.config['USERS_DB']):
        print("Создание файла пользователей...")
        users = [
            {
                "id": "1",
                "username": "admin",
                "password": generate_password_hash("admin", method='pbkdf2:sha256', salt_length=8),
                "name": "Администратор системы",
                "role": "admin",
                "token": "ADMIN001",
                "projects": []
            }
        ]
        with open(app.config['USERS_DB'], 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        print("Файл пользователей создан успешно")
    
    # Инициализация projects.json
    if not os.path.exists(app.config['PROJECTS_DB']):
        print("Создание файла проектов...")
        projects = [
            # {
            #     "id": "1",
            #     "name": "Открытие 2х новых образовательных программ.",
            #     "status": "в работе",
            #     "start_date": datetime.now().strftime("%d.%m.%Y"),
            #     "end_date": (datetime.now().replace(year=datetime.now().year + 1)).strftime("%d.%m.%Y"),
            #     "last_activity": datetime.now().strftime("%d.%m.%Y"),
            #     "direction": "Образовательные программы",
            #     "description": "Открытие 2х специальностей по направлению ИТ",
            #     "expected_result": "Подготовлены учебные документы",
            #     "supervisor_id": "2",
            #     "manager_id": "2",
            #     "team": []
            # }
        ]
        with open(app.config['PROJECTS_DB'], 'w', encoding='utf-8') as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        print("Файл проектов создан успешно")
    
    # Инициализация tasks.json
    if not os.path.exists(app.config['TASKS_DB']):
        print("Создание файла задач...")
        tasks = []
        with open(app.config['TASKS_DB'], 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print("Файл задач создан успешно")
    
    # Инициализация tokens.json
    if not os.path.exists(app.config['TOKENS_DB']):
        print("Создание файла токенов...")
        tokens = []
        with open(app.config['TOKENS_DB'], 'w', encoding='utf-8') as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
        print("Файл токенов создан успешно")

# Загрузка данных из JSON файлов
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Проверка на доступ к задаче
def can_access_task(task_id):
    """Проверка прав доступа к задаче"""
    if current_user.role == 'admin':
        return True
    
    tasks = load_data(app.config['TASKS_DB'])
    task = next((t for t in tasks if t.get('id') == task_id), None)
    
    if not task:
        return False
    
    # Если пользователь - исполнитель задачи
    if task.get('assignee_id') == current_user.id:
        return True
    
    # Проверяем доступ к проекту, к которому относится задача
    return can_access_project(task.get('project_id', ''))

# Класс пользователя для Flask-Login
class User(UserMixin):
    def __init__(self, id, username, name, role, token=None):
        self.id = id
        self.username = username
        self.name = name
        self.role = role
        self.token = token
        
    def get_projects(self):
        users = load_data(app.config['USERS_DB'])
        user = next((u for u in users if u['id'] == self.id), None)
        if user and 'projects' in user:
            return user['projects']
        return []

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    users = load_data(app.config['USERS_DB'])
    user = next((u for u in users if u['id'] == user_id), None)
    if user:
        return User(user['id'], user['username'], user['name'], user['role'], user.get('token'))
    return None

# Функция для проверки доступа к проекту
def can_access_project(project_id):
    if current_user.role == 'admin':
        return True
    
    # Загружаем проект
    projects = load_data(app.config['PROJECTS_DB'])
    project = next((p for p in projects if p.get('id') == project_id), None)
    
    if not project:
        return False
    
    # Проверяем, является ли пользователь руководителем проекта
    if current_user.role == 'manager' and (project.get('manager_id', '') == current_user.id or project.get('supervisor_id', '') == current_user.id):
        return True
    
    # Проверяем, является ли пользователь куратором проекта
    if current_user.role == 'supervisor' and project.get('supervisor_id', '') == current_user.id:
        return True
    
    # Проверяем, входит ли пользователь в команду проекта
    if current_user.role == 'worker' and current_user.id in project.get('team', []):
        return True
    
    return False

# Страница регистрации
@app.route('/register', methods=['GET', 'POST'])
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
        users = load_data(app.config['USERS_DB'])
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
        save_data(app.config['USERS_DB'], users)
        
        # Если это исполнитель, добавляем его в команду проекта
        if token_info['role'] == 'worker' and token_info['project_id']:
            projects = load_data(app.config['PROJECTS_DB'])
            for project in projects:
                if project['id'] == token_info['project_id']:
                    team = project.get('team', [])
                    if new_user['id'] not in team:
                        team.append(new_user['id'])
                        project['team'] = team
                    break
            save_data(app.config['PROJECTS_DB'], projects)
        
        # Отмечаем токен как использованный
        mark_token_as_used(token)
        
        flash('Пользователь успешно зарегистрирован')
        
        # Если пользователь уже авторизован (админ), возвращаем его в панель управления
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        else:
            # Иначе перенаправляем на страницу входа
            return redirect(url_for('login'))
    
    return render_template('register.html', roles=get_available_roles())

def get_available_roles():
    """Возвращает список доступных ролей для выбора при регистрации"""
    return [
        {'id': 'admin', 'name': 'Администратор'},
        {'id': 'manager', 'name': 'Руководитель проекта'},
        {'id': 'supervisor', 'name': 'Куратор'},
        {'id': 'worker', 'name': 'Исполнитель'}
    ]


# Функции для работы с токенами
def load_tokens():
    """Загрузка токенов из файла"""
    if not os.path.exists(app.config['TOKENS_DB']):
        return []
    with open(app.config['TOKENS_DB'], 'r', encoding='utf-8') as f:
        return json.load(f)


def save_tokens(tokens):
    """Сохранение токенов в файл"""
    with open(app.config['TOKENS_DB'], 'w', encoding='utf-8') as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def generate_token(role, project_id=None):
    """Генерация нового токена"""
    token = {
        'id': str(uuid.uuid4()),
        'role': role,
        'project_id': project_id,
        'created_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        'used': False
    }
    tokens = load_tokens()
    tokens.append(token)
    save_tokens(tokens)
    return token['id']


def validate_token(token_id):
    """Проверка валидности токена"""
    tokens = load_tokens()
    token = next((t for t in tokens if t['id'] == token_id), None)
    if token and not token['used']:
        return token
    return None


def mark_token_as_used(token_id):
    """Отметка токена как использованного"""
    tokens = load_tokens()
    for token in tokens:
        if token['id'] == token_id:
            token['used'] = True
            break
    save_tokens(tokens)


def get_user_token(user_id, project_id=None):
    """Получение или создание токена для пользователя в проекте"""
    tokens = load_tokens()
    # Ищем существующий токен для пользователя в проекте
    existing_token = next((t for t in tokens if t.get('user_id') == user_id and t.get('project_id') == project_id and not t['used']), None)
    
    if existing_token:
        return existing_token['id']
    
    # Создаем новый токен
    token = {
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'project_id': project_id,
        'created_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        'used': False
    }
    tokens.append(token)
    save_tokens(tokens)
    return token['id']


def add_task_history(task, action, user_id, users):
    """Добавление записи в историю изменений задачи"""
    # Получаем имя пользователя
    user = next((u for u in users if u['id'] == user_id), None)
    user_name = user.get('name', user.get('username', 'Неизвестный')) if user else 'Неизвестный'
    
    if 'history' not in task:
        task['history'] = []
    
    history_entry = {
        'action': action,
        'date': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        'user_id': user_id,
        'user_name': user_name
    }
    
    task['history'].append(history_entry)


def allowed_file(filename):
    """Проверка разрешенного расширения файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Маршрут для генерации токенов
@app.route('/generate_token', methods=['POST'])
@login_required
def generate_token_route():
    """Генерация токена для регистрации пользователя"""
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав для генерации токенов')
        return redirect(url_for('dashboard'))
    
    role = request.form.get('role')
    project_id = request.form.get('project_id')
    
    # Проверяем, что роль допустима
    if role not in ['admin', 'manager', 'supervisor', 'worker']:
        flash('Недопустимая роль для токена')
        return redirect(url_for('dashboard'))
    
    # Если роль worker, проверяем, что проект указан
    if role == 'worker' and not project_id:
        flash('Для исполнителя необходимо указать проект')
        return redirect(url_for('dashboard'))
    
    # Если пользователь не администратор, он может создавать только токены для исполнителей и кураторов
    if current_user.role == 'manager' and role not in ['worker', 'curator']:
        flash('Руководитель может генерировать токены только для исполнителей и кураторов')
        return redirect(url_for('dashboard'))
    
    # Если пользователь - руководитель, проверяем, что он имеет доступ к проекту
    if current_user.role == 'manager' and project_id:
        if not can_access_project(project_id):
            flash('У вас нет доступа к указанному проекту')
            return redirect(url_for('dashboard'))
    
    # Генерируем токен
    token_id = generate_token(role, project_id)
    
    flash(f'Токен успешно сгенерирован: {token_id}')
    return redirect(url_for('dashboard'))


# Главная страница - редирект на dashboard
@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

# Страница входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        users = load_data(app.config['USERS_DB'])
        
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
            if app.debug:
                if not user:
                    flash('Пользователь с таким именем не найден', 'debug')
                elif user:
                    flash('Пароль неверный', 'debug')
    
    return render_template('login.html')

# Выход из системы
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Панель управления
@app.route('/dashboard')
@login_required
def dashboard():
    projects = load_data(app.config['PROJECTS_DB'])
    tasks = load_data(app.config['TASKS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    if current_user.role == 'admin':
        # Админ видит все проекты
        visible_projects = projects
    elif current_user.role == 'manager':
        # Руководитель видит только свои проекты (где он руководитель или куратор)
        visible_projects = [p for p in projects if p.get('manager_id', '') == current_user.id or p.get('supervisor_id', '') == current_user.id]
    elif current_user.role == 'supervisor':
        # Куратор видит проекты, где он назначен куратором
        visible_projects = [p for p in projects if p.get('supervisor_id', '') == current_user.id]
    else:  # worker
        # Работник видит проекты, в которых он состоит в команде
        visible_projects = [p for p in projects if current_user.id in p.get('team', [])]
    
    # Получаем активные задачи для пользователя
    user_tasks = []
    if current_user.role == 'admin':
        user_tasks = tasks
    elif current_user.role in ['manager', 'supervisor']:
        # Руководитель и куратор видят задачи своих проектов
        project_ids = [p['id'] for p in visible_projects]
        user_tasks = [t for t in tasks if t['project_id'] in project_ids]
    else:  # worker
        # Работник видит только назначенные ему задачи
        user_tasks = [t for t in tasks if t['assignee_id'] == current_user.id and t['status'] == 'активна']
    
    # Статистика для админа и руководителей
    stats = {
        'total_projects': len(visible_projects),
        'active_projects': len([p for p in visible_projects if p['status'] == 'в работе']),
        'total_tasks': len(user_tasks),
        'active_tasks': len([t for t in user_tasks if t['status'] == 'активна']),
        'completed_tasks': len([t for t in user_tasks if t['status'] == 'завершена'])
    }
    
    # Получаем токен текущего пользователя
    user_token = current_user.token

    return render_template('dashboard.html', 
                         projects=visible_projects, 
                         tasks=user_tasks, 
                         users=users, 
                         stats=stats,
                         user_token=user_token)

# Админ-панель для управления пользователями
@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app.config['USERS_DB'])
    return render_template('admin_users.html', users=users)

# Редактирование пользователя
@app.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app.config['USERS_DB'])
    user = next((u for u in users if u['id'] == user_id), None)
    
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('admin_users'))
    
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
        
        save_data(app.config['USERS_DB'], users)
        flash('Пользователь успешно обновлен')
        return redirect(url_for('admin_users'))
    
    return render_template('edit_user.html', user=user, roles=get_available_roles())

# Удаление пользователя
@app.route('/admin/users/delete/<user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице')
        return redirect(url_for('dashboard'))
    
    users = load_data(app.config['USERS_DB'])
    
    # Проверяем, что пользователь существует и это не текущий пользователь
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        flash('Пользователь не найден')
        return redirect(url_for('admin_users'))
    
    if user_id == current_user.id:
        flash('Нельзя удалить самого себя')
        return redirect(url_for('admin_users'))
    
    # Удаляем пользователя
    users = [u for u in users if u['id'] != user_id]
    save_data(app.config['USERS_DB'], users)
    
    flash('Пользователь успешно удален')
    return redirect(url_for('admin_users'))

# ДЛЯ ОТЛАДКИ
@app.route('/reset-database')
def reset_database():
    if not app.debug:
        flash('Эта функция доступна только в режиме разработки')
        return redirect(url_for('login'))
    
    init_database(force_recreate=True)
    flash('База данных успешно сброшена. Используйте admin/admin для входа.')
    return redirect(url_for('login'))

# Инфо о проекте
@app.route('/project/<project_id>')
@login_required
def project_detail(project_id):
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard'))
    
    projects = load_data(app.config['PROJECTS_DB'])
    tasks = load_data(app.config['TASKS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard'))
    
    # Получаем задачи проекта
    project_tasks = [t for t in tasks if t.get('project_id') == project_id]
    
    # Получаем информацию о пользователях
    supervisor = next((u for u in users if u.get('id') == project.get('supervisor_id', '')), None) if project.get('supervisor_id') else None
    manager = next((u for u in users if u.get('id') == project.get('manager_id', '')), None) if project.get('manager_id') else None
    team_members = []
    if project.get('team'):
        team_members = [next((u for u in users if u.get('id') == member_id), None) for member_id in project.get('team', [])]
        team_members = [m for m in team_members if m]  # Удаляем None
    
    return render_template('project_detail.html', 
                         project=project, 
                         tasks=project_tasks, 
                         supervisor=supervisor, 
                         manager=manager, 
                         team_members=team_members,
                         users=users)

# Создание проекта
@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    # Только администратор и менеджеры могут создавать проекты
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав на создание проектов')
        return redirect(url_for('dashboard'))
    
    # Загружаем пользователей для выбора куратора, руководителя и команды
    users = load_data(app.config['USERS_DB'])
    managers = [u for u in users if u['role'] in ['admin', 'manager']]
    curators = [u for u in users if u['role'] in ['admin', 'supervisor']]
    
    if request.method == 'POST':
        # Генерируем уникальный ID для проекта
        project_id = str(uuid.uuid4())[:8]
        
        # Создаем новый проект
        new_project = {
            "id": project_id,
            "name": request.form['name'].strip(),
            "description": request.form['description'].strip(),
            "direction": request.form['direction'].strip(),
            "expected_result": request.form['expected_result'].strip(),
            "start_date": request.form['start_date'],
            "end_date": request.form['end_date'],
            "last_activity": datetime.now().strftime("%d.%m.%Y"),
            "status": request.form.get('status', 'в работе'),
            "supervisor_id": request.form['supervisor_id'],
            "manager_id": request.form['manager_id'],
            "team": request.form.getlist('team_members'),
        }
        
        # Загружаем существующие проекты и добавляем новый
        projects = load_data(app.config['PROJECTS_DB'])
        projects.append(new_project)
        save_data(app.config['PROJECTS_DB'], projects)
        
        flash('Проект успешно создан')
        return redirect(url_for('project_detail', project_id=project_id))
    
    # Для GET запроса показываем форму создания проекта
    return render_template('create_project.html', users=users, managers=managers, curators=curators)

# Создание задачи
@app.route('/project/<project_id>/create_task', methods=['GET', 'POST'])
@login_required
def create_task(project_id):
    # Проверяем доступ к проекту
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard'))
    
    # Только менеджеры и администраторы могут создавать задачи
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав на создание задач')
        return redirect(url_for('project_detail', project_id=project_id))
    
    projects = load_data(app.config['PROJECTS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard'))
    
    # Получаем пользователей, которым можно назначить задачу
    eligible_users = []
    if current_user.role == 'admin':
        eligible_users = users
    else:
        # Руководитель видит всех в команде проекта + себя
        team_member_ids = project.get('team', []) + [project.get('manager_id')]
        eligible_users = [u for u in users if u['id'] in team_member_ids]
    
    if request.method == 'POST':
        # Validate that start_date <= deadline
        start_date = request.form.get('start_date', datetime.now().strftime("%d.%m.%Y"))
        deadline = request.form['deadline']
        
        if start_date and deadline:
            try:
                start_dt = parse_date(start_date)
                deadline_dt = parse_date(deadline)
                if start_dt > deadline_dt:
                    flash('Дата начала не может быть позже даты дедлайна')
                    return render_template('create_task.html', project=project, users=eligible_users)
            except:
                flash('Некорректный формат даты')
                return render_template('create_task.html', project=project, users=eligible_users)
        
        task = {
            "id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "title": request.form['title'].strip(),
            "description": request.form['description'].strip(),
            "assignee_id": request.form['assignee_id'],
            "created_by": current_user.id,
            "created_at": datetime.now().strftime("%d.%m.%Y"),
            "start_date": start_date,
            "deadline": request.form['deadline'],
            "status": "активна",
            "completion_date": ""
        }
        
        tasks = load_data(app.config['TASKS_DB'])
        tasks.append(task)
        save_data(app.config['TASKS_DB'], tasks)
        
        # Обновляем дату последней активности проекта
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app.config['PROJECTS_DB'], projects)
        
        flash('Задача успешно создана')
        return redirect(url_for('project_detail', project_id=project_id))
    
    return render_template('create_task.html', project=project, users=eligible_users)


# API для задач
@app.route('/api/project/<project_id>/tasks', methods=['GET'])
@login_required
def api_get_tasks_by_project(project_id):
    """Список задач по проекту"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403
    
    tasks = load_data(app.config['TASKS_DB'])
    project_tasks = [t for t in tasks if t.get('project_id') == project_id]
    
    # Добавляем информацию о пользователях к задачам
    users = load_data(app.config['USERS_DB'])
    user_map = {u['id']: u for u in users}
    
    for task in project_tasks:
        assignee = user_map.get(task.get('assignee_id'))
        if assignee:
            # Вместо ФИО возвращаем токен пользователя в проекте
            token = get_user_token(task.get('assignee_id'), project_id)
            task['assignee_token'] = token
            task['assignee_name'] = assignee.get('name', assignee.get('username', ''))
        else:
            task['assignee_token'] = None
            task['assignee_name'] = 'Не назначен'
    
    return jsonify(project_tasks)


@app.route('/api/project/<project_id>/tasks', methods=['POST'])
@login_required
def api_create_task(project_id):
    """Создание задачи"""
    # Проверяем доступ к проекту
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403
    
    # Только менеджеры, кураторы и администраторы могут создавать задачи
    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав на создание задач'}), 403
    
    projects = load_data(app.config['PROJECTS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404
    
    # Получаем данные из запроса
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    assignee_id = request.form.get('assignee_id')
    deadline = request.form.get('deadline')
    
    if not title:
        return jsonify({'error': 'Название задачи обязательно'}), 400
    
    # Проверяем, что исполнитель является участником проекта
    if assignee_id:
        user = next((u for u in users if u['id'] == assignee_id), None)
        if not user:
            return jsonify({'error': 'Исполнитель не найден'}), 404
        
        if assignee_id not in project.get('team', []) and assignee_id != project.get('manager_id') and assignee_id != project.get('supervisor_id'):
            return jsonify({'error': 'Исполнитель не является участником проекта'}), 400
    else:
        # Если исполнитель не указан, назначаем текущего пользователя (если он участник проекта)
        if current_user.id in project.get('team', []) or current_user.id == project.get('manager_id') or current_user.id == project.get('supervisor_id'):
            assignee_id = current_user.id
        else:
            return jsonify({'error': 'Необходимо указать исполнителя'}), 400
    
    # Validate that start_date <= deadline
    start_date = request.form.get('start_date', datetime.now().strftime("%d.%m.%Y"))
    deadline = request.form.get('deadline')
    
    if start_date and deadline:
        try:
            start_dt = parse_date(start_date)
            deadline_dt = parse_date(deadline)
            if start_dt > deadline_dt:
                return jsonify({'error': 'Дата начала не может быть позже даты дедлайна'}), 400
        except:
            return jsonify({'error': 'Некорректный формат даты'}), 400
    
    # Проверка дат: deadline не может быть раньше текущей даты
    if deadline:
        try:
            deadline_dt = parse_date(deadline)
            current_dt = datetime.now()
            if deadline_dt < current_dt:
                return jsonify({'error': 'Дата дедлайна не может быть в прошлом'}), 400
        except:
            return jsonify({'error': 'Некорректный формат даты'}), 400
    
    # Создаем задачу
    task = {
        "id": str(uuid.uuid4())[:8],
        "project_id": project_id,
        "title": title,
        "description": description,
        "assignee_id": assignee_id,
        "created_by": current_user.id,
        "created_at": datetime.now().strftime("%d.%m.%Y"),
        "start_date": start_date,
        "deadline": deadline or "",
        "status": "активна",
        "completion_date": ""
    }
    
    # Сохраняем задачу
    tasks = load_data(app.config['TASKS_DB'])
    tasks.append(task)
    save_data(app.config['TASKS_DB'], tasks)
    
    # Обновляем дату последней активности проекта
    project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
    for i, p in enumerate(projects):
        if p.get('id') == project_id:
            projects[i] = project
            break
    save_data(app.config['PROJECTS_DB'], projects)
    
    return jsonify({'success': True, 'message': 'Задача успешно создана', 'task': task})


# Обновление задачи
@app.route('/task/<task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Обновление статуса задачи"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        flash('У вас нет доступа к этой задаче')
        return redirect(url_for('dashboard'))
    
    tasks = load_data(app.config['TASKS_DB'])
    task = next((t for t in tasks if t.get('id') == task_id), None)
    
    if not task:
        flash('Задача не найдена')
        return redirect(url_for('dashboard'))
    
    new_status = request.form.get('status')
    if new_status not in ['активна', 'завершена', 'отложена']:
        flash('Недопустимый статус задачи')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Обновляем статус задачи
    task['status'] = new_status
    
    # Если задача завершается, устанавливаем дату завершения
    if new_status == 'завершена' and task.get('status') != 'завершена':
        task['completion_date'] = datetime.now().strftime("%d.%m.%Y")
    elif new_status != 'завершена':
        task['completion_date'] = ""
    
    # Сохраняем изменения
    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break
    
    save_data(app.config['TASKS_DB'], tasks)
    
    # Обновляем дату последней активности проекта
    projects = load_data(app.config['PROJECTS_DB'])
    project = next((p for p in projects if p.get('id') == task.get('project_id')), None)
    if project:
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project.get('id'):
                projects[i] = project
                break
        save_data(app.config['PROJECTS_DB'], projects)
    
    flash('Статус задачи успешно обновлен')
    return redirect(request.referrer or url_for('dashboard'))


# Обновление задачи (включая изменение ответственного)
@app.route('/task/<task_id>/update', methods=['POST'])
@login_required
def update_task(task_id):
    """Обновление задачи (включая изменение ответственного)"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403
    
    tasks = load_data(app.config['TASKS_DB'])
    task = next((t for t in tasks if t.get('id') == task_id), None)
    
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404
    
    # Только администраторы, менеджеры и кураторы могут редактировать задачи
    project_id = task.get('project_id')
    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав на редактирование задачи'}), 403
    
    # Проверяем доступ к проекту
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к проекту задачи'}), 403
    
    # Получаем новые значения
    new_assignee_id = request.form.get('assignee_id')
    new_title = request.form.get('title')
    new_description = request.form.get('description')
    new_start_date = request.form.get('start_date')
    new_deadline = request.form.get('deadline')
    
    # Проверка дат: start_date <= deadline
    if new_start_date and new_deadline:
        try:
            start_dt = parse_date(new_start_date)
            deadline_dt = parse_date(new_deadline)
            if start_dt > deadline_dt:
                return jsonify({'error': 'Дата начала не может быть позже даты дедлайна'}), 400
        except:
            return jsonify({'error': 'Некорректный формат даты'}), 400
    
    # Обновляем поля задачи
    original_task = task.copy()  # Сохраняем оригинальное состояние для сравнения
    
    if new_assignee_id and new_assignee_id != task.get('assignee_id'):
        # Проверяем, что новый ответственный существует и является участником проекта
        users = load_data(app.config['USERS_DB'])
        user = next((u for u in users if u['id'] == new_assignee_id), None)
        if not user:
            return jsonify({'error': 'Назначаемый пользователь не найден'}), 404
        
        # Проверяем, что пользователь является участником проекта
        projects = load_data(app.config['PROJECTS_DB'])
        project = next((p for p in projects if p['id'] == project_id), None)
        if project and new_assignee_id not in project.get('team', []) and new_assignee_id != project.get('manager_id') and new_assignee_id != project.get('supervisor_id'):
            return jsonify({'error': 'Назначаемый пользователь не является участником проекта'}), 400
        
        task['assignee_id'] = new_assignee_id
        # Добавляем запись в историю
        add_task_history(task, f'Изменен ответственный с {original_task.get("assignee_id", "не назначен")} на {new_assignee_id}', current_user.id, users)
    
    if new_title and new_title != task.get('title'):
        old_title = task.get('title', '')
        task['title'] = new_title.strip()
        # Добавляем запись в историю
        users = load_data(app.config['USERS_DB'])
        add_task_history(task, f'Изменено название с "{old_title}" на "{new_title}"', current_user.id, users)
    
    if new_description and new_description != task.get('description'):
        old_description = task.get('description', '')
        task['description'] = new_description.strip()
        # Добавляем запись в историю
        users = load_data(app.config['USERS_DB'])
        add_task_history(task, f'Изменено описание', current_user.id, users)
    
    if new_start_date and new_start_date != task.get('start_date'):
        old_start_date = task.get('start_date', '')
        task['start_date'] = new_start_date
        # Добавляем запись в историю
        users = load_data(app.config['USERS_DB'])
        add_task_history(task, f'Изменена дата начала с "{old_start_date}" на "{new_start_date}"', current_user.id, users)
    
    if new_deadline and new_deadline != task.get('deadline'):
        old_deadline = task.get('deadline', '')
        task['deadline'] = new_deadline
        # Добавляем запись в историю
        users = load_data(app.config['USERS_DB'])
        add_task_history(task, f'Изменен дедлайн с "{old_deadline}" на "{new_deadline}"', current_user.id, users)
    
    if 'status' in request.form and request.form['status'] != task.get('status'):
        old_status = task.get('status', '')
        new_status = request.form['status']
        task['status'] = new_status
        # Добавляем запись в историю
        users = load_data(app.config['USERS_DB'])
        add_task_history(task, f'Изменен статус с "{old_status}" на "{new_status}"', current_user.id, users)
    
    # Сохраняем изменения
    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break
    
    save_data(app.config['TASKS_DB'], tasks)
    
    # Обновляем дату последней активности проекта
    if project:
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app.config['PROJECTS_DB'], projects)
    
    return jsonify({'success': True, 'message': 'Задача успешно обновлена'})


# Загрузка файла к задаче
@app.route('/task/<task_id>/upload_file', methods=['POST'])
@login_required
def upload_task_file(task_id):
    """Загрузка файла к задаче (до закрытия)"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403
    
    tasks = load_data(app.config['TASKS_DB'])
    task = next((t for t in tasks if t.get('id') == task_id), None)
    
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404
    
    # Проверяем, что задача еще не закрыта (статус не "завершена")
    if task.get('status') == 'завершена':
        return jsonify({'error': 'Нельзя загружать файлы к завершенной задаче'}), 400
    
    # Проверяем, что пользователь имеет право (исполнитель задачи, менеджер, куратор или админ)
    project_id = task.get('project_id')
    if current_user.role not in ['admin'] and current_user.id != task.get('assignee_id'):
        if not can_access_project(project_id) and current_user.role not in ['manager', 'curator']:
            return jsonify({'error': 'У вас нет прав для загрузки файлов к этой задаче'}), 403
    
    # Проверяем, что файл был загружен
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не был загружен'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не был выбран'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Добавляем уникальный префикс к имени файла, чтобы избежать конфликта
        unique_filename = f"{task_id}_{uuid.uuid4().hex[:8]}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(filepath)
        
        # Добавляем информацию о файле к задаче
        file_info = {
            'filename': filename,
            'unique_filename': unique_filename,
            'uploaded_by': current_user.id,
            'uploaded_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            'size': os.path.getsize(filepath)
        }
        
        # Загружаем задачи снова на случай, если были изменения
        tasks = load_data(app.config['TASKS_DB'])
        task = next((t for t in tasks if t.get('id') == task_id), None)
        
        if not task:
            # Удаляем загруженный файл, если задача не найдена
            os.remove(filepath)
            return jsonify({'error': 'Задача не найдена'}), 404
        
        # Добавляем файл в список файлов задачи
        if 'files' not in task:
            task['files'] = []
        task['files'].append(file_info)
        
        # Сохраняем изменения
        for i, t in enumerate(tasks):
            if t.get('id') == task_id:
                tasks[i] = task
                break
        
        save_data(app.config['TASKS_DB'], tasks)
        
        return jsonify({'success': True, 'message': 'Файл успешно загружен', 'file': file_info})
    else:
        return jsonify({'error': 'Недопустимый тип файла'}), 400


# Страница и API для деталей задачи
@app.route('/task/<task_id>')
@login_required
def task_detail(task_id):
    """Страница деталей задачи"""
    if not can_access_task(task_id):
        flash('У вас нет доступа к этой задаче')
        return redirect(url_for('dashboard'))
    
    tasks = load_data(app.config['TASKS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        flash('Задача не найдена')
        return redirect(url_for('dashboard'))
    
    # Получаем информацию о пользователе-исполнителе
    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None
    
    # Получаем информацию о пользователе-создателе
    creator = next((u for u in users if u['id'] == task.get('created_by')), None) if task.get('created_by') else None
    
    return render_template('task_detail.html', task=task, assignee=assignee, creator=creator)


@app.route('/api/task/<task_id>')
@login_required
def api_task_detail(task_id):
    """API для полных данных задачи: описание, дата, ответственный, файлы, история изменений"""
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403
    
    tasks = load_data(app.config['TASKS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404
    
    # Получаем информацию о пользователе-исполнителе
    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None
    if assignee:
        # Вместо ФИО возвращаем токен пользователя в проекте
        token = get_user_token(task.get('assignee_id'), task.get('project_id'))
        task['assignee_token'] = token
        task['assignee_name'] = assignee.get('name', assignee.get('username', ''))
    else:
        task['assignee_token'] = None
        task['assignee_name'] = 'Не назначен'
    
    # Получаем информацию о пользователе-создателе
    creator = next((u for u in users if u['id'] == task.get('created_by')), None) if task.get('created_by') else None
    if creator:
        task['creator_name'] = creator.get('name', creator.get('username', ''))
    else:
        task['creator_name'] = 'Неизвестно'
    
    # Добавляем историю изменений (пока просто базовая информация)
    # В реальной системе это может быть отдельный журнал изменений
    task['history'] = [
        {
            'action': 'Создание задачи',
            'date': task.get('created_at', ''),
            'user_id': task.get('created_by'),
            'user_name': task.get('creator_name', 'Неизвестно')
        }
    ]
    
    # Если у задачи есть файлы, возвращаем их
    if 'files' not in task:
        task['files'] = []
    
    return jsonify(task)


# Редактирование проекта
@app.route('/project/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    # Проверка прав доступа
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard'))
    
    # Только администратор и ответственные за проект могут редактировать
    projects = load_data(app.config['PROJECTS_DB'])
    project = next((p for p in projects if p['id'] == project_id), None)
    
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard'))
    
    # Проверка прав на редактирование
    if current_user.role not in ['admin'] and current_user.id != project['manager_id']:
        flash('У вас нет прав на редактирование этого проекта')
        return redirect(url_for('project_detail', project_id=project_id))
    
    users = load_data(app.config['USERS_DB'])
    managers = [u for u in users if u['role'] in ['admin', 'manager']]
    
    if request.method == 'POST':
        # Обновляем данные проекта
        project['name'] = request.form['name'].strip()
        project['description'] = request.form['description'].strip()
        project['direction'] = request.form['direction'].strip()
        project['expected_result'] = request.form['expected_result'].strip()
        # project['start_date'] = request.form.get('start_date', None)
        project['end_date'] = request.form.get('end_date', None)
        project['status'] = request.form.get('status', 'в работе')
        project['supervisor_id'] = request.form.get('supervisor_id', None)
        project['manager_id'] = request.form.get('manager_id', None)
        project['team'] = request.form.getlist('team_members')
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        
        # Сохраняем изменения
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        
        save_data(app.config['PROJECTS_DB'], projects)
        flash('Проект успешно обновлен')
        return redirect(url_for('project_detail', project_id=project_id))
    
    return render_template('edit_project.html', project=project, users=users, managers=managers)


# API для управления командой проекта
@app.route('/api/project/<project_id>/team', methods=['GET'])
@login_required
def api_get_project_team(project_id):
    """API списка участников проекта с токенами вместо ФИО"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403
    
    projects = load_data(app.config['PROJECTS_DB'])
    users = load_data(app.config['USERS_DB'])
    
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404
    
    # Получаем участников команды проекта
    team_member_ids = project.get('team', [])
    team_members = []
    
    for user_id in team_member_ids:
        user = next((u for u in users if u['id'] == user_id), None)
        if user:
            # Получаем токен для пользователя в проекте
            token = get_user_token(user_id, project_id)
            team_member = {
                'id': user['id'],
                'token': token,  # Вместо ФИО возвращаем токен
                'role': user.get('role', ''),
                'name': user.get('name', '')  # Оставляем имя для внутреннего использования
            }
            team_members.append(team_member)
    
    return jsonify(team_members)


@app.route('/project/<project_id>/add_member', methods=['POST'])
@login_required
def add_project_member(project_id):
    """Назначить участника проекта (доступно куратору/менеджеру)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403
    
    # Проверяем права - только администратор, менеджер или куратор могут добавлять участников
    projects = load_data(app.config['PROJECTS_DB'])
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404
    
    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав для добавления участников в проект'}), 403
    
    # Дополнительная проверка: куратор должен быть куратором этого проекта
    if current_user.role == 'curator' and project.get('supervisor_id') != current_user.id:
        return jsonify({'error': 'Вы не являетесь куратором этого проекта'}), 403
    
    user_id = request.form.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не указан ID пользователя'}), 400
    
    # Проверяем, что пользователь существует
    users = load_data(app.config['USERS_DB'])
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Добавляем пользователя в команду проекта, если его там еще нет
    team = project.get('team', [])
    if user_id not in team:
        team.append(user_id)
        project['team'] = team
        
        # Сохраняем изменения
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app.config['PROJECTS_DB'], projects)
        
        return jsonify({'success': True, 'message': 'Участник успешно добавлен в проект'})
    else:
        return jsonify({'error': 'Пользователь уже является участником проекта'}), 400


@app.route('/project/<project_id>/remove_member/<user_id>', methods=['POST'])
@login_required
def remove_project_member(project_id, user_id):
    """Удалить участника проекта (доступно куратору/менеджеру)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403
    
    # Проверяем права - только администратор, менеджер или куратор могут удалять участников
    projects = load_data(app.config['PROJECTS_DB'])
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404
    
    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав для удаления участников из проекта'}), 403
    
    # Дополнительная проверка: куратор должен быть куратором этого проекта
    if current_user.role == 'curator' and project.get('supervisor_id') != current_user.id:
        return jsonify({'error': 'Вы не являетесь куратором этого проекта'}), 403
    
    # Проверяем, что пользователь существует
    users = load_data(app.config['USERS_DB'])
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Удаляем пользователя из команды проекта
    team = project.get('team', [])
    if user_id in team:
        team.remove(user_id)
        project['team'] = team
        
        # Сохраняем изменения
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app.config['PROJECTS_DB'], projects)
        
        return jsonify({'success': True, 'message': 'Участник успешно удален из проекта'})
    else:
        return jsonify({'error': 'Пользователь не является участником проекта'}), 400


if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)