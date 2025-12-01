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

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Создание директории для базы данных, если её нет
os.makedirs(app.config['DATABASE_PATH'], exist_ok=True)

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
    def __init__(self, id, username, name, role):
        self.id = id
        self.username = username
        self.name = name
        self.role = role
        
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
        return User(user['id'], user['username'], user['name'], user['role'])
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
    
    # Проверяем, является ли пользователь руководителем или куратором проекта
    if current_user.role == 'manager' and (project.get('manager_id', '') == current_user.id or project.get('supervisor_id', '') == current_user.id):
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
        
        # Создание нового пользователя
        new_user = {
            "id": str(uuid.uuid4())[:8],
            "username": username,
            "password": generate_password_hash(password),
            "name": name,
            "role": token_info['role'],
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
    if role not in ['admin', 'manager', 'worker']:
        flash('Недопустимая роль для токена')
        return redirect(url_for('dashboard'))
    
    # Если роль worker, проверяем, что проект указан
    if role == 'worker' and not project_id:
        flash('Для исполнителя необходимо указать проект')
        return redirect(url_for('dashboard'))
    
    # Если пользователь не администратор, он может создавать только токены для исполнителей
    if current_user.role == 'manager' and role != 'worker':
        flash('Руководитель может генерировать токены только для исполнителей')
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
            
            user_obj = User(user_id, username, name, role)
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
    else:  # worker
        # Работник видит проекты, в которых он состоит в команде
        visible_projects = [p for p in projects if current_user.id in p.get('team', [])]
    
    # Получаем активные задачи для пользователя
    user_tasks = []
    if current_user.role == 'admin':
        user_tasks = tasks
    elif current_user.role == 'manager':
        # Руководитель видит задачи своих проектов
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
    
    return render_template('dashboard.html', 
                         projects=visible_projects, 
                         tasks=user_tasks, 
                         users=users, 
                         stats=stats)

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
    return render_template('create_project.html', users=users, managers=managers)

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
        task = {
            "id": str(uuid.uuid4())[:8],
            "project_id": project_id,
            "title": request.form['title'].strip(),
            "description": request.form['description'].strip(),
            "assignee_id": request.form['assignee_id'],
            "created_by": current_user.id,
            "created_at": datetime.now().strftime("%d.%m.%Y"),
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
    if current_user.role not in ['admin'] and current_user.id != project.get('manager_id'):
        flash('У вас нет прав на редактирование этого проекта')
        return redirect(url_for('project_detail', project_id=project_id))
    
    users = load_data(app.config['USERS_DB'])
    managers = [u for u in users if u['role'] in ['admin', 'manager']]
    
    if request.method == 'POST':
        # Обновляем данные проекта, используя значения из формы или сохраняя текущие
        project['name'] = request.form.get('name', project['name']).strip()
        project['description'] = request.form.get('description', project['description']).strip()
        project['direction'] = request.form.get('direction', project['direction']).strip()
        project['expected_result'] = request.form.get('expected_result', project['expected_result']).strip()
        
        # Проверяем, есть ли даты в форме, иначе оставляем текущие значения
        if 'start_date' in request.form:
            project['start_date'] = request.form['start_date']
        if 'end_date' in request.form:
            project['end_date'] = request.form['end_date']
        
        project['status'] = request.form.get('status', 'в работе')
        
        # Проверяем, есть ли ID руководителей в форме, иначе оставляем текущие значения
        if 'supervisor_id' in request.form:
            project['supervisor_id'] = request.form['supervisor_id']
        if 'manager_id' in request.form:
            project['manager_id'] = request.form['manager_id']
        
        # Проверяем, есть ли список участников команды в форме, иначе оставляем текущий
        if 'team_members' in request.form:
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

if __name__ == '__main__':
    init_database()
    app.run(debug=True)