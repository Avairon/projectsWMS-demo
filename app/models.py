from flask_login import UserMixin
import json
import os
from config import Config

app_config = Config()

# Загрузка данных из JSON файлов
def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Класс пользователя для Flask-Login
class User(UserMixin):
    def __init__(self, id, username, name, role, token=None):
        self.id = id
        self.username = username
        self.name = name
        self.role = role
        self.token = token
        
    def get_projects(self):
        users = load_data(app_config.USERS_DB)
        user = next((u for u in users if u['id'] == self.id), None)
        if user and 'projects' in user:
            return user['projects']
        return []

def load_user(user_id):
    users = load_data(app_config.USERS_DB)
    user = next((u for u in users if u['id'] == user_id), None)
    if user:
        return User(user['id'], user['username'], user['name'], user['role'], user.get('token'))
    return None