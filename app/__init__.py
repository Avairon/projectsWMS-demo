from flask import Flask
from flask_login import LoginManager
import os
from config import Config

app = None

def create_app():
    global app
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    app.config.from_object(Config)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице'

    app.config['UPLOAD_FOLDER'] = os.path.join(Config.BASE_DIR, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['DATABASE_PATH'] = Config.DATABASE_PATH

    os.makedirs(app.config['DATABASE_PATH'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.projects import projects_bp
    from app.routes.tasks import tasks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)

    @login_manager.user_loader
    def load_user_callback(user_id):
        from app.models import load_user
        return load_user(user_id)

    @app.route('/generate_token', methods=['POST'])
    def generate_token_route():
        from flask import request, flash, redirect, url_for
        from flask_login import current_user
        from app.utils import generate_token, can_access_project
        
        if not current_user.is_authenticated:
            flash('Необходимо авторизоваться', 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['admin', 'manager']:
            flash('У вас нет прав для генерации токенов', 'error')
            return redirect(url_for('dashboard.dashboard'))
        
        role = request.form.get('role')
        project_id = request.form.get('project_id')
        
        if role not in ['admin', 'manager', 'supervisor', 'worker']:
            flash('Недопустимая роль для токена', 'error')
            return redirect(url_for('auth.profile'))
        
        if role == 'worker' and not project_id:
            flash('Для исполнителя необходимо указать проект', 'error')
            return redirect(url_for('auth.profile'))
        
        if current_user.role == 'manager' and role not in ['worker', 'supervisor']:
            flash('Руководитель может генерировать токены только для исполнителей и кураторов', 'error')
            return redirect(url_for('auth.profile'))
        
        if current_user.role == 'manager' and project_id:
            if not can_access_project(project_id):
                flash('У вас нет доступа к указанному проекту', 'error')
                return redirect(url_for('auth.profile'))
        
        token_id = generate_token(role, project_id)
        
        flash(f'Токен успешно сгенерирован: {token_id}', 'success')
        return redirect(url_for('auth.profile'))

    @app.route('/uploads/<executor_dir>/<filename>')
    def uploaded_file(executor_dir, filename):
        from flask import send_from_directory
        import os
        from config import Config
        
        uploads_dir = os.path.join(Config.BASE_DIR, 'uploads')
        executor_path = os.path.join(uploads_dir, executor_dir)
        
        # Security check: prevent directory traversal
        if '..' in executor_dir or '..' in filename:
            from flask import abort
            return abort(404)
        
        # Check if the file exists
        filepath = os.path.join(executor_path, filename)
        if not os.path.exists(filepath):
            from flask import abort
            return abort(404)
        
        return send_from_directory(executor_path, filename, as_attachment=True)

    return app
