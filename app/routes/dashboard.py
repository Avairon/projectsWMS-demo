from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.utils import load_data, save_data, can_access_project, get_available_roles
from config import Config
import uuid
from datetime import datetime

app_config = Config()
dashboard_bp = Blueprint('dashboard', __name__) 
# FIX ROUTES


# Главная страница - редирект на dashboard
@dashboard_bp.route('/')
@login_required
def index():
    return redirect(url_for('dashboard.dashboard'))

# Панель управления
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    projects = load_data(app_config.PROJECTS_DB)
    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)
    
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