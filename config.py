# Настройка
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-for-project-registry-123456'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'database')
    
    # Создаем директорию для базы данных при импорте
    os.makedirs(DATABASE_PATH, exist_ok=True)
    
    USERS_DB = os.path.join(DATABASE_PATH, 'users.json')
    PROJECTS_DB = os.path.join(DATABASE_PATH, 'projects.json')
    TASKS_DB = os.path.join(DATABASE_PATH, 'tasks.json')
    TOKENS_DB = os.path.join(DATABASE_PATH, 'tokens.json')