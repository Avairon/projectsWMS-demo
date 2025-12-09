from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.utils import load_data, save_data, can_access_project, can_access_task, add_task_history, allowed_file
from config import Config
import uuid
from datetime import datetime
from dateutil.parser import parse as parse_date
from werkzeug.utils import secure_filename
import os

app_config = Config()
tasks_bp = Blueprint('tasks', __name__)

# Создание задачи
@tasks_bp.route('/project/<project_id>/create_task', methods=['GET', 'POST'])
@login_required
def create_task(project_id):
    # Проверяем доступ к проекту
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard.dashboard'))

    # Только менеджеры и администраторы могут создавать задачи
    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав на создание задач')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    projects = load_data(app_config.PROJECTS_DB)
    users = load_data(app_config.USERS_DB)

    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard.dashboard'))

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

        tasks = load_data(app_config.TASKS_DB)
        tasks.append(task)
        save_data(app_config.TASKS_DB, tasks)

        # Обновляем дату последней активности проекта
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

        flash('Задача успешно создана')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    return render_template('create_task.html', project=project, users=eligible_users)


# API для задач
@tasks_bp.route('/api/project/<project_id>/tasks', methods=['GET'])
@login_required
def api_get_tasks_by_project(project_id):
    """Список задач по проекту"""
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    tasks = load_data(app_config.TASKS_DB)
    project_tasks = [t for t in tasks if t.get('project_id') == project_id]

    # Добавляем информацию о пользователях к задачам
    users = load_data(app_config.USERS_DB)
    user_map = {u['id']: u for u in users}

    for task in project_tasks:
        assignee = user_map.get(task.get('assignee_id'))
        if assignee:
            # Вместо ФИО возвращаем токен пользователя в проекте
            from app.utils import get_user_token
            token = get_user_token(task.get('assignee_id'), project_id)
            task['assignee_token'] = token
            task['assignee_name'] = assignee.get('name', assignee.get('username', ''))
        else:
            task['assignee_token'] = None
            task['assignee_name'] = 'Не назначен'

    return jsonify(project_tasks)


@tasks_bp.route('/api/project/<project_id>/tasks', methods=['POST'])
@login_required
def api_create_task(project_id):
    """Создание задачи"""
    # Проверяем доступ к проекту
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    # Только менеджеры, кураторы и администраторы могут создавать задачи
    if current_user.role not in ['admin', 'manager', 'curator']:
        return jsonify({'error': 'У вас нет прав на создание задач'}), 403

    projects = load_data(app_config.PROJECTS_DB)
    users = load_data(app_config.USERS_DB)

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
    tasks = load_data(app_config.TASKS_DB)
    tasks.append(task)
    save_data(app_config.TASKS_DB, tasks)

    # Обновляем дату последней активности проекта
    project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
    for i, p in enumerate(projects):
        if p.get('id') == project_id:
            projects[i] = project
            break
    save_data(app_config.PROJECTS_DB, projects)

    return jsonify({'success': True, 'message': 'Задача успешно создана', 'task': task})


# Обновление задачи
@tasks_bp.route('/task/<task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Обновление статуса задачи"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        flash('У вас нет доступа к этой задаче')
        return redirect(url_for('dashboard.dashboard'))

    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)

    if not task:
        flash('Задача не найдена')
        return redirect(url_for('dashboard.dashboard'))

    new_status = request.form.get('status')
    if new_status not in ['активна', 'завершена', 'отложена']:
        flash('Недопустимый статус задачи')
        return redirect(request.referrer or url_for('dashboard.dashboard'))

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

    save_data(app_config.TASKS_DB, tasks)

    # Обновляем дату последней активности проекта
    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p.get('id') == task.get('project_id')), None)
    if project:
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project.get('id'):
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    flash('Статус задачи успешно обновлен')
    return redirect(request.referrer or url_for('dashboard.dashboard'))


# Обновление задачи (включая изменение ответственного)
@tasks_bp.route('/task/<task_id>/update', methods=['POST'])
@login_required
def update_task(task_id):
    """Обновление задачи (включая изменение ответственного)"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
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
        users = load_data(app_config.USERS_DB)
        user = next((u for u in users if u['id'] == new_assignee_id), None)
        if not user:
            return jsonify({'error': 'Назначаемый пользователь не найден'}), 404

        # Проверяем, что пользователь является участником проекта
        projects = load_data(app_config.PROJECTS_DB)
        project = next((p for p in projects if p['id'] == project_id), None)
        if project and new_assignee_id not in project.get('team', []) and new_assignee_id != project.get('manager_id') and new_assignee_id != project.get('supervisor_id'):
            return jsonify({'error': 'Назначаемый пользователь не является участником проекта'}), 400

        task['assignee_id'] = new_assignee_id
        # Добавляем запись в историю
        from app.utils import add_task_history
        add_task_history(task, f'Изменен ответственный с {original_task.get("assignee_id", "не назначен")} на {new_assignee_id}', current_user.id, users)

    if new_title and new_title != task.get('title'):
        old_title = task.get('title', '')
        task['title'] = new_title.strip()
        # Добавляем запись в историю
        users = load_data(app_config.USERS_DB)
        add_task_history(task, f'Изменено название с "{old_title}" на "{new_title}"', current_user.id, users)

    if new_description and new_description != task.get('description'):
        old_description = task.get('description', '')
        task['description'] = new_description.strip()
        # Добавляем запись в историю
        users = load_data(app_config.USERS_DB)
        add_task_history(task, f'Изменено описание', current_user.id, users)

    if new_start_date and new_start_date != task.get('start_date'):
        old_start_date = task.get('start_date', '')
        task['start_date'] = new_start_date
        # Добавляем запись в историю
        users = load_data(app_config.USERS_DB)
        add_task_history(task, f'Изменена дата начала с "{old_start_date}" на "{new_start_date}"', current_user.id, users)

    if new_deadline and new_deadline != task.get('deadline'):
        old_deadline = task.get('deadline', '')
        task['deadline'] = new_deadline
        # Добавляем запись в историю
        users = load_data(app_config.USERS_DB)
        add_task_history(task, f'Изменен дедлайн с "{old_deadline}" на "{new_deadline}"', current_user.id, users)

    if 'status' in request.form and request.form['status'] != task.get('status'):
        old_status = task.get('status', '')
        new_status = request.form['status']
        task['status'] = new_status
        # Добавляем запись в историю
        users = load_data(app_config.USERS_DB)
        add_task_history(task, f'Изменен статус с "{old_status}" на "{new_status}"', current_user.id, users)

    # Сохраняем изменения
    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break

    save_data(app_config.TASKS_DB, tasks)

    # Обновляем дату последней активности проекта
    if project:
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    return jsonify({'success': True, 'message': 'Задача успешно обновлена'})


# Загрузка файла к задаче
@tasks_bp.route('/task/<task_id>/upload_file', methods=['POST'])
@login_required
def upload_task_file(task_id):
    """Загрузка файла к задаче (до закрытия)"""
    # Проверяем права доступа к задаче
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
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
        filepath = os.path.join(app_config.BASE_DIR, 'uploads', unique_filename)

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
        tasks = load_data(app_config.TASKS_DB)
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

        save_data(app_config.TASKS_DB, tasks)

        return jsonify({'success': True, 'message': 'Файл успешно загружен', 'file': file_info})
    else:
        return jsonify({'error': 'Недопустимый тип файла'}), 400


# Страница и API для деталей задачи
@tasks_bp.route('/task/<task_id>')
@login_required
def task_detail(task_id):
    """Страница деталей задачи"""
    if not can_access_task(task_id):
        flash('У вас нет доступа к этой задаче')
        return redirect(url_for('dashboard.dashboard'))

    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)

    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        flash('Задача не найдена')
        return redirect(url_for('dashboard.dashboard'))

    # Получаем информацию о пользователе-исполнителе
    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None

    # Получаем информацию о пользователе-создателе
    creator = next((u for u in users if u['id'] == task.get('created_by')), None) if task.get('created_by') else None

    return render_template('task_detail.html', task=task, assignee=assignee, creator=creator)


@tasks_bp.route('/api/task/<task_id>')
@login_required
def api_task_detail(task_id):
    """API для полных данных задачи: описание, дата, ответственный, файлы, история изменений"""
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)

    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404

    # Получаем информацию о пользователе-исполнителе
    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None
    if assignee:
        # Вместо ФИО возвращаем токен пользователя в проекте
        from app.utils import get_user_token
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