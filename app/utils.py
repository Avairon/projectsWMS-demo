import json
import os
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from dateutil.parser import parse as parse_date
from flask_login import current_user

app_config = Config()

# Инициализация JSON файлов с данными, если их нет
def init_database(force_recreate=False):
    """Инициализация базы данных. Если force_recreate=True, пересоздает файлы даже если они существуют"""
    
    # Если нужно принудительно пересоздать базу данных
    if force_recreate:
        print("Принудительное пересоздание базы данных...")
        if os.path.exists(app_config.USERS_DB):
            os.remove(app_config.USERS_DB)
        if os.path.exists(app_config.PROJECTS_DB):
            os.remove(app_config.PROJECTS_DB)
        if os.path.exists(app_config.TASKS_DB):
            os.remove(app_config.TASKS_DB)

    # Инициализация users.json
    if not os.path.exists(app_config.USERS_DB):
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
        with open(app_config.USERS_DB, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        print("Файл пользователей создан успешно")
    
    # Инициализация projects.json
    if not os.path.exists(app_config.PROJECTS_DB):
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
        with open(app_config.PROJECTS_DB, 'w', encoding='utf-8') as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        print("Файл проектов создан успешно")
    
    # Инициализация tasks.json
    if not os.path.exists(app_config.TASKS_DB):
        print("Создание файла задач...")
        tasks = []
        with open(app_config.TASKS_DB, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print("Файл задач создан успешно")
    
    # Инициализация tokens.json
    if not os.path.exists(app_config.TOKENS_DB):
        print("Создание файла токенов...")
        tokens = []
        with open(app_config.TOKENS_DB, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
        print("Файл токенов создан успешно")


def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def can_access_task(task_id):
    """Проверка прав доступа к задаче"""
    if current_user.role == 'admin':
        return True
    
    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)
    
    if not task:
        return False
    
    # Если пользователь - исполнитель задачи
    if task.get('assignee_id') == current_user.id:
        return True
    
    # Проверяем доступ к проекту, к которому относится задача
    return can_access_project(task.get('project_id', ''))


def can_access_project(project_id):
    if current_user.role == 'admin':
        return True
    
    # Загружаем проект
    projects = load_data(app_config.PROJECTS_DB)
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
    if not os.path.exists(app_config.TOKENS_DB):
        return []
    with open(app_config.TOKENS_DB, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_tokens(tokens):
    """Сохранение токенов в файл"""
    with open(app_config.TOKENS_DB, 'w', encoding='utf-8') as f:
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
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS