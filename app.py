# Все либы(flask + зависимости)

from flask import Flask, render_template
from flask_login import LoginManager
import os
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Конфигурация для загрузки файлов
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Создание директории для базы данных, если её нет
os.makedirs(app.config['DATABASE_PATH'], exist_ok=True)
# Создание директории для загрузки файлов, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Допустимые расширения файлов
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

# Регистрация маршрутов
from app.models import load_user
from app.utils import init_database, generate_token
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.projects import projects_bp
from app.routes.tasks import tasks_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(tasks_bp)

# Загрузчик пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return load_user(user_id)

# Маршрут для генерации токенов
@app.route('/generate_token', methods=['POST'])
def generate_token_route():
    """Генерация токена для регистрации пользователя"""
    from flask import request, flash, redirect, url_for
    from flask_login import current_user
    from app.utils import validate_token
    from app.models import load_data
    from config import Config
    
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав для генерации токенов')
        return redirect(url_for('dashboard.dashboard'))
    
    role = request.form.get('role')
    project_id = request.form.get('project_id')
    
    # Проверяем, что роль допустима
    if role not in ['admin', 'manager', 'supervisor', 'worker']:
        flash('Недопустимая роль для токена')
        return redirect(url_for('dashboard.dashboard'))
    
    # Если роль worker, проверяем, что проект указан
    if role == 'worker' and not project_id:
        flash('Для исполнителя необходимо указать проект')
        return redirect(url_for('dashboard.dashboard'))
    
    # Если пользователь не администратор, он может создавать только токены для исполнителей и кураторов
    if current_user.role == 'manager' and role not in ['worker', 'supervisor']:
        flash('Руководитель может генерировать токены только для исполнителей и кураторов')
        return redirect(url_for('dashboard.dashboard'))
    
    # Если пользователь - руководитель, проверяем, что он имеет доступ к проекту
    if current_user.role == 'manager' and project_id:
        from app.utils import can_access_project
        if not can_access_project(project_id):
            flash('У вас нет доступа к указанному проекту')
            return redirect(url_for('dashboard.dashboard'))
    
    # Генерируем токен
    token_id = generate_token(role, project_id)
    
    flash(f'Токен успешно сгенерирован: {token_id}')
    return redirect(url_for('dashboard.dashboard'))


if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=True)