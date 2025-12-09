from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.utils import load_data, save_data, can_access_project, can_access_task
from config import Config
import uuid
from datetime import datetime
from dateutil.parser import parse as parse_date

app_config = Config()
projects_bp = Blueprint('projects', __name__)

# Инфо о проекте
@projects_bp.route('/project/<project_id>')
@login_required
def project_detail(project_id):
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard.dashboard'))

    projects = load_data(app_config.PROJECTS_DB)
    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)

    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard.dashboard'))

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
@projects_bp.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    # Только администратор и менеджеры могут создавать проекты
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав на создание проектов')
        return redirect(url_for('dashboard.dashboard'))

    # Загружаем пользователей для выбора куратора, руководителя и команды
    users = load_data(app_config.USERS_DB)
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
        projects = load_data(app_config.PROJECTS_DB)
        projects.append(new_project)
        save_data(app_config.PROJECTS_DB, projects)

        flash('Проект успешно создан')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    # Для GET запроса показываем форму создания проекта
    return render_template('create_project.html', users=users, managers=managers, curators=curators)


# Редактирование проекта
@projects_bp.route('/project/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    # Проверка прав доступа
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard.dashboard'))

    # Только администратор и ответственные за проект могут редактировать
    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == project_id), None)

    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard.dashboard'))

    # Проверка прав на редактирование
    if current_user.role not in ['admin'] and current_user.id != project['manager_id']:
        flash('У вас нет прав на редактирование этого проекта')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    users = load_data(app_config.USERS_DB)
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

        save_data(app_config.PROJECTS_DB, projects)
        flash('Проект успешно обновлен')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    return render_template('edit_project.html', project=project, users=users, managers=managers)


# API для управления командой проекта
@projects_bp.route('/api/project/<project_id>/team', methods=['GET'])
@login_required
def api_get_project_team(project_id):
    """API списка участников проекта с токенами вместо ФИО"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    projects = load_data(app_config.PROJECTS_DB)
    users = load_data(app_config.USERS_DB)

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
            from app.utils import get_user_token
            token = get_user_token(user_id, project_id)
            team_member = {
                'id': user['id'],
                'token': token,  # Вместо ФИО возвращаем токен
                'role': user.get('role', ''),
                'name': user.get('name', '')  # Оставляем имя для внутреннего использования
            }
            team_members.append(team_member)

    return jsonify(team_members)


@projects_bp.route('/project/<project_id>/add_member', methods=['POST'])
@login_required
def add_project_member(project_id):
    """Назначить участника проекта (доступно куратору/менеджеру)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    # Проверяем права - только администратор, менеджер или куратор могут добавлять участников
    projects = load_data(app_config.PROJECTS_DB)
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
    users = load_data(app_config.USERS_DB)
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
        save_data(app_config.PROJECTS_DB, projects)

        return jsonify({'success': True, 'message': 'Участник успешно добавлен в проект'})
    else:
        return jsonify({'error': 'Пользователь уже является участником проекта'}), 400


@projects_bp.route('/project/<project_id>/remove_member/<user_id>', methods=['POST'])
@login_required
def remove_project_member(project_id, user_id):
    """Удалить участника проекта (доступно куратору/менеджеру)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    # Проверяем права - только администратор, менеджер или куратор могут удалять участников
    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404

    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав для удаления участников из проекта'}), 403

    # Дополнительная проверка: куратор должен быть куратором этого проекта
    if current_user.role == 'curator' and project.get('supervisor_id') != current_user.id:
        return jsonify({'error': 'Вы не являетесь куратором этого проекта'}), 403

    # Проверяем, что пользователь существует
    users = load_data(app_config.USERS_DB)
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
        save_data(app_config.PROJECTS_DB, projects)

        return jsonify({'success': True, 'message': 'Участник успешно удален из проекта'})
    else:
        return jsonify({'error': 'Пользователь не является участником проекта'}), 400


@projects_bp.route('/project/<project_id>/add_member_by_token', methods=['POST'])
@login_required
def add_project_member_by_token(project_id):
    """Добавить участника проекта по токену (доступно куратору/менеджеру)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    # Проверяем права - только администратор, менеджер или куратор могут добавлять участников
    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404

    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав для добавления участников в проект'}), 403

    # Дополнительная проверка: куратор должен быть куратором этого проекта
    if current_user.role == 'curator' and project.get('supervisor_id') != current_user.id:
        return jsonify({'error': 'Вы не являетесь куратором этого проекта'}), 403

    token = request.form.get('token')
    if not token:
        return jsonify({'error': 'Не указан токен пользователя'}), 400

    # Проверяем токен
    from app.utils import validate_token, mark_token_as_used
    token_info = validate_token(token)
    if not token_info:
        return jsonify({'error': 'Неверный или использованный токен'}), 400

    # Проверяем, что токен предназначен для исполнителя
    if token_info['role'] != 'worker':
        return jsonify({'error': 'Токен должен быть для исполнителя'}), 400

    # Проверяем, что токен предназначен для этого проекта
    if token_info['project_id'] != project_id:
        return jsonify({'error': 'Токен не относится к этому проекту'}), 400

    # Находим пользователя по токену
    users = load_data(app_config.USERS_DB)
    user = next((u for u in users if u.get('token') == token), None)
    if not user:
        return jsonify({'error': 'Пользователь с таким токеном не найден'}), 404

    # Добавляем пользователя в команду проекта, если его там еще нет
    team = project.get('team', [])
    if user['id'] not in team:
        team.append(user['id'])
        project['team'] = team

        # Сохраняем изменения
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

        # Отмечаем токен как использованный
        mark_token_as_used(token)

        return jsonify({'success': True, 'message': 'Участник успешно добавлен в проект'})
    else:
        return jsonify({'error': 'Пользователь уже является участником проекта'}), 400


@projects_bp.route('/project/<project_id>/update_curator', methods=['POST'])
@login_required
def update_project_curator(project_id):
    """Изменить куратора проекта (доступно админу и менеджеру проекта)"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404

    # Проверяем права: только админ или менеджер проекта могут изменить куратора
    if current_user.role != 'admin' and current_user.id != project.get('manager_id'):
        return jsonify({'error': 'У вас нет прав для изменения куратора проекта'}), 403

    new_curator_id = request.form.get('curator_id')
    if not new_curator_id:
        return jsonify({'error': 'Не указан ID нового куратора'}), 400

    # Проверяем, что новый куратор существует
    users = load_data(app_config.USERS_DB)
    user = next((u for u in users if u['id'] == new_curator_id), None)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Проверяем, что пользователь имеет роль куратора
    if user['role'] != 'supervisor':
        return jsonify({'error': 'Пользователь не является куратором'}), 400

    # Обновляем куратора проекта
    old_curator_id = project.get('supervisor_id')
    project['supervisor_id'] = new_curator_id

    # Сохраняем изменения
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            projects[i] = project
            break
    save_data(app_config.PROJECTS_DB, projects)

    # Если старый куратор был в команде, удаляем его оттуда
    if old_curator_id and old_curator_id in project.get('team', []):
        team = project.get('team', [])
        if old_curator_id in team:
            team.remove(old_curator_id)
        project['team'] = team
        # Обновляем проект в списке
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    # Добавляем нового куратора в команду, если его там еще нет
    team = project.get('team', [])
    if new_curator_id not in team:
        team.append(new_curator_id)
        project['team'] = team
        # Обновляем проект в списке
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    return jsonify({'success': True, 'message': 'Куратор проекта успешно изменен'})


@projects_bp.route('/project/<project_id>/update_manager', methods=['POST'])
@login_required
def update_project_manager(project_id):
    """Изменить менеджера проекта (доступно только админу)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'У вас нет прав для изменения менеджера проекта'}), 403

    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == project_id), None)
    if not project:
        return jsonify({'error': 'Проект не найден'}), 404

    new_manager_id = request.form.get('manager_id')
    if not new_manager_id:
        return jsonify({'error': 'Не указан ID нового менеджера'}), 400

    # Проверяем, что новый менеджер существует
    users = load_data(app_config.USERS_DB)
    user = next((u for u in users if u['id'] == new_manager_id), None)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Проверяем, что пользователь имеет роль менеджера
    if user['role'] != 'manager':
        return jsonify({'error': 'Пользователь не является менеджером'}), 400

    # Обновляем менеджера проекта
    old_manager_id = project.get('manager_id')
    project['manager_id'] = new_manager_id

    # Сохраняем изменения
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            projects[i] = project
            break
    save_data(app_config.PROJECTS_DB, projects)

    # Если старый менеджер был в команде, удаляем его оттуда
    if old_manager_id and old_manager_id in project.get('team', []):
        team = project.get('team', [])
        if old_manager_id in team:
            team.remove(old_manager_id)
        project['team'] = team
        # Обновляем проект в списке
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    # Добавляем нового менеджера в команду, если его там еще нет
    team = project.get('team', [])
    if new_manager_id not in team:
        team.append(new_manager_id)
        project['team'] = team
        # Обновляем проект в списке
        for i, p in enumerate(projects):
            if p['id'] == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    return jsonify({'success': True, 'message': 'Менеджер проекта успешно изменен'})