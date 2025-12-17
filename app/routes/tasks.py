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


@tasks_bp.route('/project/<project_id>/create_task', methods=['GET', 'POST'])
@login_required
def create_task(project_id):
    if not can_access_project(project_id):
        flash('У вас нет доступа к этому проекту')
        return redirect(url_for('dashboard.dashboard'))

    if current_user.role not in ['admin', 'manager']:
        flash('У вас нет прав на создание задач')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    projects = load_data(app_config.PROJECTS_DB)
    users = load_data(app_config.USERS_DB)

    project = next((p for p in projects if p.get('id') == project_id), None)
    if not project:
        flash('Проект не найден')
        return redirect(url_for('dashboard.dashboard'))

    eligible_users = []
    if current_user.role == 'admin':
        eligible_users = users
    else:
        team_member_ids = project.get('team', []) + [project.get('manager_id')]
        eligible_users = [u for u in users if u['id'] in team_member_ids]

    if request.method == 'POST':
        start_date = request.form.get('start_date', '')
        deadline = request.form['deadline']
        
        # Конвертируем даты в нужный формат, если они предоставлены
        if start_date:
            try:
                start_dt = parse_date(start_date)
                start_date = start_dt.strftime("%d.%m.%Y")
            except:
                flash('Некорректный формат даты начала')
                return render_template('create_task.html', project=project, users=eligible_users)
        else:
            start_date = datetime.now().strftime("%d.%m.%Y")
        
        if deadline:
            try:
                deadline_dt = parse_date(deadline)
                deadline = deadline_dt.strftime("%d.%m.%Y")
            except:
                flash('Некорректный формат даты дедлайна')
                return render_template('create_task.html', project=project, users=eligible_users)
        
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
            "deadline": deadline,
            "status": "активна",
            "completion_date": ""
        }

        tasks = load_data(app_config.TASKS_DB)
        tasks.append(task)
        save_data(app_config.TASKS_DB, tasks)

        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

        flash('Задача успешно создана')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    return render_template('create_task.html', project=project, users=eligible_users)


@tasks_bp.route('/api/project/<project_id>/tasks', methods=['GET'])
@login_required
def api_get_tasks_by_project(project_id):
    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к этому проекту'}), 403

    tasks = load_data(app_config.TASKS_DB)
    project_tasks = [t for t in tasks if t.get('project_id') == project_id]

    users = load_data(app_config.USERS_DB)
    user_map = {u['id']: u for u in users}

    for task in project_tasks:
        assignee = user_map.get(task.get('assignee_id'))
        if assignee:
            from app.utils import get_user_token
            token = get_user_token(task.get('assignee_id'), project_id)
            task['assignee_token'] = token
            task['assignee_name'] = assignee.get('name', assignee.get('username', ''))
        else:
            task['assignee_token'] = None
            task['assignee_name'] = 'Не назначен'

    return jsonify(project_tasks)


@tasks_bp.route('/task/<task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
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

    task['status'] = new_status

    if new_status == 'завершена' and task.get('status') != 'завершена':
        task['completion_date'] = datetime.now().strftime("%d.%m.%Y")
    elif new_status != 'завершена':
        task['completion_date'] = ""

    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break

    save_data(app_config.TASKS_DB, tasks)

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


@tasks_bp.route('/task/<task_id>/update', methods=['POST'])
@login_required
def update_task(task_id):
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)

    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404

    project_id = task.get('project_id')
    if current_user.role not in ['admin', 'manager', 'supervisor']:
        return jsonify({'error': 'У вас нет прав на редактирование задачи'}), 403

    if not can_access_project(project_id):
        return jsonify({'error': 'У вас нет доступа к проекту задачи'}), 403

    new_assignee_id = request.form.get('assignee_id')
    new_title = request.form.get('title')
    new_description = request.form.get('description')
    new_start_date = request.form.get('start_date')
    new_deadline = request.form.get('deadline')
    
    # Конвертируем даты в нужный формат, если они предоставлены
    if new_start_date:
        try:
            start_dt = parse_date(new_start_date)
            new_start_date = start_dt.strftime("%d.%m.%Y")
        except:
            return jsonify({'error': 'Некорректный формат даты начала'}), 400
    
    if new_deadline:
        try:
            deadline_dt = parse_date(new_deadline)
            new_deadline = deadline_dt.strftime("%d.%m.%Y")
        except:
            return jsonify({'error': 'Некорректный формат даты дедлайна'}), 400

    if new_start_date and new_deadline:
        try:
            start_dt = parse_date(new_start_date)
            deadline_dt = parse_date(new_deadline)
            if start_dt > deadline_dt:
                return jsonify({'error': 'Дата начала не может быть позже даты дедлайна'}), 400
        except:
            return jsonify({'error': 'Некорректный формат даты'}), 400

    original_task = task.copy()
    users = load_data(app_config.USERS_DB)

    if new_assignee_id and new_assignee_id != task.get('assignee_id'):
        user = next((u for u in users if u['id'] == new_assignee_id), None)
        if not user:
            return jsonify({'error': 'Назначаемый пользователь не найден'}), 404

        projects = load_data(app_config.PROJECTS_DB)
        project = next((p for p in projects if p['id'] == project_id), None)
        if project and new_assignee_id not in project.get('team', []) and new_assignee_id != project.get('manager_id') and new_assignee_id != project.get('supervisor_id'):
            return jsonify({'error': 'Назначаемый пользователь не является участником проекта'}), 400

        task['assignee_id'] = new_assignee_id
        add_task_history(task, f'Изменен ответственный', current_user.id, users)

    if new_title and new_title != task.get('title'):
        task['title'] = new_title.strip()
        add_task_history(task, f'Изменено название', current_user.id, users)

    if new_description is not None and new_description != task.get('description'):
        task['description'] = new_description.strip()
        add_task_history(task, f'Изменено описание', current_user.id, users)

    if new_start_date and new_start_date != task.get('start_date'):
        task['start_date'] = new_start_date
        add_task_history(task, f'Изменена дата начала', current_user.id, users)

    if new_deadline and new_deadline != task.get('deadline'):
        task['deadline'] = new_deadline
        add_task_history(task, f'Изменен дедлайн', current_user.id, users)

    if 'status' in request.form and request.form['status'] != task.get('status'):
        new_status = request.form['status']
        task['status'] = new_status
        add_task_history(task, f'Изменен статус на "{new_status}"', current_user.id, users)
        if new_status == 'завершена':
            task['completion_date'] = datetime.now().strftime("%d.%m.%Y")
        else:
            task['completion_date'] = ""

    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break

    save_data(app_config.TASKS_DB, tasks)

    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p.get('id') == project_id), None)
    if project:
        project['last_activity'] = datetime.now().strftime("%d.%m.%Y")
        for i, p in enumerate(projects):
            if p.get('id') == project_id:
                projects[i] = project
                break
        save_data(app_config.PROJECTS_DB, projects)

    return jsonify({'success': True, 'message': 'Задача успешно обновлена'})


@tasks_bp.route('/task/<task_id>/upload_file', methods=['POST'])
@login_required
def upload_task_file(task_id):
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)

    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404

    if task.get('status') == 'завершена':
        return jsonify({'error': 'Нельзя загружать файлы к завершенной задаче'}), 400

    project_id = task.get('project_id')
    if current_user.role not in ['admin'] and current_user.id != task.get('assignee_id'):
        if not can_access_project(project_id) and current_user.role not in ['manager', 'supervisor']:
            return jsonify({'error': 'У вас нет прав для загрузки файлов к этой задаче'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не был загружен'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не был выбран'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Get user info to create executor-specific directory
        users = load_data(app_config.USERS_DB)
        assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None)
        if not assignee:
            return jsonify({'error': 'Исполнитель задачи не найден'}), 404
        
        # Create directory named after executor if it doesn't exist
        executor_name = assignee.get('name', assignee.get('username', 'unknown'))
        executor_safe_name = secure_filename(executor_name.replace(" ", "_"))
        executor_dir = os.path.join(app_config.BASE_DIR, 'uploads', executor_safe_name)
        os.makedirs(executor_dir, exist_ok=True)
        
        unique_filename = f"{task_id}_{uuid.uuid4().hex[:8]}_{filename}"
        filepath = os.path.join(executor_dir, unique_filename)

        file.save(filepath)

        file_info = {
            'filename': filename,
            'unique_filename': unique_filename,
            'uploaded_by': current_user.id,
            'uploaded_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            'size': os.path.getsize(filepath),
            'executor_dir': executor_safe_name
        }

        tasks = load_data(app_config.TASKS_DB)
        task = next((t for t in tasks if t.get('id') == task_id), None)

        if not task:
            os.remove(filepath)
            return jsonify({'error': 'Задача не найдена'}), 404

        if 'files' not in task:
            task['files'] = []
        task['files'].append(file_info)

        for i, t in enumerate(tasks):
            if t.get('id') == task_id:
                tasks[i] = task
                break

        save_data(app_config.TASKS_DB, tasks)

        return jsonify({'success': True, 'message': 'Файл успешно загружен', 'file': file_info})
    else:
        return jsonify({'error': 'Недопустимый тип файла'}), 400


@tasks_bp.route('/task/<task_id>/report', methods=['POST'])
@login_required
def report_task(task_id):
    """Route for executors to report on their tasks with comments and files"""
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)

    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404

    # Check if current user is the assignee of the task
    if current_user.id != task.get('assignee_id') and current_user.role not in ['admin', 'manager', 'supervisor']:
        return jsonify({'error': 'Только исполнитель задачи может отправить отчет'}), 403

    comment = request.form.get('comment', '').strip()
    
    # Process file upload if present
    file_info = None
    if 'report_file' in request.files:
        file = request.files['report_file']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Get user info to create executor-specific directory
            users = load_data(app_config.USERS_DB)
            assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None)
            if not assignee:
                return jsonify({'error': 'Исполнитель задачи не найден'}), 404
            
            # Create directory named after executor if it doesn't exist
            executor_name = assignee.get('name', assignee.get('username', 'unknown'))
            executor_safe_name = secure_filename(executor_name.replace(" ", "_"))
            executor_dir = os.path.join(app_config.BASE_DIR, 'uploads', executor_safe_name)
            os.makedirs(executor_dir, exist_ok=True)
            
            unique_filename = f"report_{task_id}_{uuid.uuid4().hex[:8]}_{filename}"
            filepath = os.path.join(executor_dir, unique_filename)

            file.save(filepath)

            file_info = {
                'filename': filename,
                'unique_filename': unique_filename,
                'uploaded_by': current_user.id,
                'uploaded_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                'size': os.path.getsize(filepath),
                'executor_dir': executor_safe_name
            }
    
    # Load task again in case file was uploaded
    tasks = load_data(app_config.TASKS_DB)
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        # If file was uploaded, remove it
        if file_info:
            filepath = os.path.join(app_config.BASE_DIR, 'uploads', file_info['executor_dir'], file_info['unique_filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
        return jsonify({'error': 'Задача не найдена'}), 404

    # Initialize reports array if not exists
    if 'reports' not in task:
        task['reports'] = []

    # Create report entry
    report_entry = {
        'id': str(uuid.uuid4()),
        'comment': comment,
        'file': file_info,
        'reported_by': current_user.id,
        'reported_at': datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    task['reports'].append(report_entry)

    # Update the task in the database
    for i, t in enumerate(tasks):
        if t.get('id') == task_id:
            tasks[i] = task
            break

    save_data(app_config.TASKS_DB, tasks)

    # Add to task history
    users = load_data(app_config.USERS_DB)
    add_task_history(task, f'Отчет: {comment[:50]}...' if len(comment) > 50 else f'Отчет: {comment}', current_user.id, users)

    return jsonify({
        'success': True, 
        'message': 'Отчет успешно отправлен',
        'report': report_entry
    })


@tasks_bp.route('/task/<task_id>')
@login_required
def task_detail(task_id):
    if not can_access_task(task_id):
        flash('У вас нет доступа к этой задаче')
        return redirect(url_for('dashboard.dashboard'))

    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)

    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        flash('Задача не найдена')
        return redirect(url_for('dashboard.dashboard'))

    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None
    creator = next((u for u in users if u['id'] == task.get('created_by')), None) if task.get('created_by') else None

    # Ensure reports are included in the task
    if 'reports' not in task:
        task['reports'] = []

    return render_template('task_detail.html', task=task, assignee=assignee, creator=creator)


@tasks_bp.route('/api/task/<task_id>')
@login_required
def api_task_detail(task_id):
    if not can_access_task(task_id):
        return jsonify({'error': 'У вас нет доступа к этой задаче'}), 403

    tasks = load_data(app_config.TASKS_DB)
    users = load_data(app_config.USERS_DB)

    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404

    assignee = next((u for u in users if u['id'] == task.get('assignee_id')), None) if task.get('assignee_id') else None
    if assignee:
        from app.utils import get_user_token
        token = get_user_token(task.get('assignee_id'), task.get('project_id'))
        task['assignee_token'] = token
        task['assignee_name'] = assignee.get('name', assignee.get('username', ''))
    else:
        task['assignee_token'] = None
        task['assignee_name'] = 'Не назначен'

    creator = next((u for u in users if u['id'] == task.get('created_by')), None) if task.get('created_by') else None
    if creator:
        task['creator_name'] = creator.get('name', creator.get('username', ''))
    else:
        task['creator_name'] = 'Неизвестно'

    if 'history' not in task:
        task['history'] = [
            {
                'action': 'Создание задачи',
                'date': task.get('created_at', ''),
                'user_id': task.get('created_by'),
                'user_name': task.get('creator_name', 'Неизвестно')
            }
        ]

    if 'files' not in task:
        task['files'] = []

    projects = load_data(app_config.PROJECTS_DB)
    project = next((p for p in projects if p['id'] == task.get('project_id')), None)
    team_users = []
    if project:
        team_ids = project.get('team', [])
        if project.get('manager_id'):
            team_ids.append(project.get('manager_id'))
        if project.get('supervisor_id'):
            team_ids.append(project.get('supervisor_id'))
        team_users = [{'id': u['id'], 'name': u['name']} for u in users if u['id'] in team_ids]
    
    task['team_users'] = team_users

    # Include reports if they exist
    if 'reports' not in task:
        task['reports'] = []

    return jsonify(task)
