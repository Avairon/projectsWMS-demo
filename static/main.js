document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    initGanttChart();
    initTooltips();
});

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const tabId = this.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            this.classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');

            if (tabId === 'gantt') {
                setTimeout(() => renderGanttChart(), 100);
            }
        });
    });
}

let ganttScale = 40;
let ganttStartDate = null;
let ganttEndDate = null;

function initGanttChart() {
    if (typeof tasksData === 'undefined' || typeof projectStartDate === 'undefined') {
        return;
    }

    const startParts = projectStartDate.split('.');
    const endParts = projectEndDate.split('.');

    if (startParts.length === 3) {
        ganttStartDate = new Date(startParts[2], startParts[1] - 1, startParts[0]);
    } else {
        ganttStartDate = new Date();
    }

    if (endParts.length === 3) {
        ganttEndDate = new Date(endParts[2], endParts[1] - 1, endParts[0]);
    } else {
        ganttEndDate = new Date();
        ganttEndDate.setMonth(ganttEndDate.getMonth() + 3);
    }

    if (isNaN(ganttStartDate.getTime())) {
        ganttStartDate = new Date();
    }
    if (isNaN(ganttEndDate.getTime())) {
        ganttEndDate = new Date();
        ganttEndDate.setMonth(ganttEndDate.getMonth() + 3);
    }
}

function renderGanttChart() {
    const timeline = document.getElementById('gantt-timeline');
    const tasksContainer = document.getElementById('gantt-tasks');

    if (!timeline || !tasksContainer) return;

    timeline.innerHTML = '';
    tasksContainer.innerHTML = '';

    if (!ganttStartDate || !ganttEndDate) {
        initGanttChart();
    }

    const days = getDaysBetween(ganttStartDate, ganttEndDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const labelWidth = 200;
    timeline.innerHTML = `<div style="min-width: ${labelWidth}px; border-right: 2px solid var(--gray-300);"></div>`;

    for (let i = 0; i <= days; i++) {
        const date = new Date(ganttStartDate);
        date.setDate(date.getDate() + i);

        const dayOfWeek = date.getDay();
        const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
        const isToday = date.getTime() === today.getTime();

        const dayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

        const timelineItem = document.createElement('div');
        timelineItem.className = 'gantt-timeline-item';
        if (isWeekend) timelineItem.classList.add('weekend');
        if (isToday) timelineItem.classList.add('today');
        timelineItem.style.minWidth = ganttScale + 'px';
        timelineItem.innerHTML = `
            <div>${date.getDate()}</div>
            <div style="font-size: 0.65rem; opacity: 0.7">${dayNames[dayOfWeek]}</div>
        `;
        timeline.appendChild(timelineItem);
    }

    if (typeof tasksData === 'undefined' || !tasksData.length) {
        tasksContainer.innerHTML = '<p class="no-data" style="padding: 20px;">Нет задач для отображения на графике</p>';
        return;
    }

    tasksData.forEach(task => {
        const row = document.createElement('div');
        row.className = 'gantt-row';
        row.dataset.taskId = task.id;

        const label = document.createElement('div');
        label.className = 'gantt-task-label';
        label.textContent = task.title;
        label.title = task.title;

        const barContainer = document.createElement('div');
        barContainer.className = 'gantt-task-bar-container';

        let taskStart, taskEnd;

        if (task.start_date) {
            const startParts = task.start_date.split('.');
            if (startParts.length === 3) {
                taskStart = new Date(startParts[2], startParts[1] - 1, startParts[0]);
            }
        }

        if (task.deadline) {
            const endParts = task.deadline.split('.');
            if (endParts.length === 3) {
                taskEnd = new Date(endParts[2], endParts[1] - 1, endParts[0]);
            }
        }

        if (!taskStart || isNaN(taskStart.getTime())) {
            taskStart = new Date(ganttStartDate);
        }
        if (!taskEnd || isNaN(taskEnd.getTime())) {
            taskEnd = new Date(taskStart);
            taskEnd.setDate(taskEnd.getDate() + 7);
        }

        const startOffset = getDaysBetween(ganttStartDate, taskStart);
        const duration = getDaysBetween(taskStart, taskEnd) + 1;

        const bar = document.createElement('div');
        bar.className = 'gantt-task-bar';

        let statusClass = 'status-active';
        if (task.status === 'завершена') statusClass = 'status-completed';
        else if (task.status === 'отложена') statusClass = 'status-paused';
        bar.classList.add(statusClass);

        bar.style.left = (startOffset * ganttScale) + 'px';
        bar.style.width = (duration * ganttScale) + 'px';
        bar.dataset.taskId = task.id;
        bar.dataset.startDate = formatDate(taskStart);
        bar.dataset.endDate = formatDate(taskEnd);

        const leftHandle = document.createElement('div');
        leftHandle.className = 'resize-handle left';

        const rightHandle = document.createElement('div');
        rightHandle.className = 'resize-handle right';

        bar.appendChild(leftHandle);
        bar.appendChild(rightHandle);

        initDragAndDrop(bar, barContainer);
        initResize(bar, leftHandle, rightHandle, barContainer);

        bar.addEventListener('click', function (e) {
            if (!e.target.classList.contains('resize-handle')) {
                openTaskModal(task.id);
            }
        });

        const assignee = typeof usersData !== 'undefined' ?
            usersData.find(u => u.id === task.assignee_id) : null;

        bar.addEventListener('mouseenter', function (e) {
            showTooltip(e, task, assignee);
        });

        bar.addEventListener('mousemove', function (e) {
            moveTooltip(e);
        });

        bar.addEventListener('mouseleave', function () {
            hideTooltip();
        });

        barContainer.appendChild(bar);
        row.appendChild(label);
        row.appendChild(barContainer);
        tasksContainer.appendChild(row);
    });
}

function getDaysBetween(start, end) {
    const oneDay = 24 * 60 * 60 * 1000;
    return Math.round((end - start) / oneDay);
}

function formatDate(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function initDragAndDrop(bar, container) {
    let isDragging = false;
    let startX = 0;
    let originalLeft = 0;

    bar.addEventListener('mousedown', function (e) {
        if (e.target.classList.contains('resize-handle')) return;

        isDragging = true;
        startX = e.clientX;
        originalLeft = parseInt(bar.style.left) || 0;
        bar.classList.add('dragging');

        e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
        if (!isDragging) return;

        const deltaX = e.clientX - startX;
        const newLeft = originalLeft + deltaX;

        const snappedLeft = Math.round(newLeft / ganttScale) * ganttScale;
        bar.style.left = Math.max(0, snappedLeft) + 'px';
    });

    document.addEventListener('mouseup', function () {
        if (!isDragging) return;

        isDragging = false;
        bar.classList.remove('dragging');

        const newStartOffset = parseInt(bar.style.left) / ganttScale;
        const duration = parseInt(bar.style.width) / ganttScale;

        const newStartDate = new Date(ganttStartDate);
        newStartDate.setDate(newStartDate.getDate() + newStartOffset);

        const newEndDate = new Date(newStartDate);
        newEndDate.setDate(newEndDate.getDate() + duration - 1);

        bar.dataset.startDate = formatDate(newStartDate);
        bar.dataset.endDate = formatDate(newEndDate);

        updateTaskDates(bar.dataset.taskId, formatDate(newStartDate), formatDate(newEndDate));
    });
}

function initResize(bar, leftHandle, rightHandle, container) {
    let isResizing = false;
    let resizeDirection = null;
    let startX = 0;
    let originalLeft = 0;
    let originalWidth = 0;

    function startResize(e, direction) {
        isResizing = true;
        resizeDirection = direction;
        startX = e.clientX;
        originalLeft = parseInt(bar.style.left) || 0;
        originalWidth = parseInt(bar.style.width) || ganttScale;
        bar.classList.add('dragging');

        e.preventDefault();
        e.stopPropagation();
    }

    leftHandle.addEventListener('mousedown', (e) => startResize(e, 'left'));
    rightHandle.addEventListener('mousedown', (e) => startResize(e, 'right'));

    document.addEventListener('mousemove', function (e) {
        if (!isResizing) return;

        const deltaX = e.clientX - startX;

        if (resizeDirection === 'left') {
            const newLeft = Math.round((originalLeft + deltaX) / ganttScale) * ganttScale;
            const newWidth = originalWidth - (newLeft - originalLeft);

            if (newWidth >= ganttScale && newLeft >= 0) {
                bar.style.left = newLeft + 'px';
                bar.style.width = newWidth + 'px';
            }
        } else if (resizeDirection === 'right') {
            const newWidth = Math.round((originalWidth + deltaX) / ganttScale) * ganttScale;

            if (newWidth >= ganttScale) {
                bar.style.width = newWidth + 'px';
            }
        }
    });

    document.addEventListener('mouseup', function () {
        if (!isResizing) return;

        isResizing = false;
        resizeDirection = null;
        bar.classList.remove('dragging');

        const newStartOffset = parseInt(bar.style.left) / ganttScale;
        const duration = parseInt(bar.style.width) / ganttScale;

        const newStartDate = new Date(ganttStartDate);
        newStartDate.setDate(newStartDate.getDate() + newStartOffset);

        const newEndDate = new Date(newStartDate);
        newEndDate.setDate(newEndDate.getDate() + duration - 1);

        bar.dataset.startDate = formatDate(newStartDate);
        bar.dataset.endDate = formatDate(newEndDate);

        updateTaskDates(bar.dataset.taskId, formatDate(newStartDate), formatDate(newEndDate));
    });
}

function updateTaskDates(taskId, startDate, endDate) {
    console.log('Updating task dates:', taskId, startDate, endDate);

    // TODO: Backend - Реализовать API endpoint для обновления дат задачи
    // PUT /api/tasks/<task_id>/dates
    // Body: { start_date: string, deadline: string }
    // Ожидаемый ответ: { success: boolean, task: Task }

    showNotification('Даты задачи обновлены (требуется backend)', 'success');
}

function ganttZoom(direction) {
    if (direction === 'in') {
        ganttScale = Math.min(80, ganttScale + 10);
    } else {
        ganttScale = Math.max(20, ganttScale - 10);
    }
    renderGanttChart();
}

function ganttToday() {
    const chart = document.getElementById('gantt-chart');
    if (!chart) return;

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const daysFromStart = getDaysBetween(ganttStartDate, today);
    const scrollPosition = (daysFromStart * ganttScale) - (chart.clientWidth / 2) + 200;

    chart.scrollLeft = Math.max(0, scrollPosition);
}

function initTooltips() {
}

function showTooltip(e, task, assignee) {
    const tooltip = document.getElementById('gantt-tooltip');
    if (!tooltip) return;

    const assigneeName = assignee ? assignee.name : 'Не назначен';

    tooltip.innerHTML = `
        <div class="tooltip-title">${task.title}</div>
        <div class="tooltip-info">
            <div>Исполнитель: ${assigneeName}</div>
            <div>Статус: ${task.status}</div>
            <div>Дедлайн: ${task.deadline || 'Не указан'}</div>
        </div>
    `;

    tooltip.style.left = (e.clientX + 15) + 'px';
    tooltip.style.top = (e.clientY + 15) + 'px';
    tooltip.classList.add('visible');
}

function moveTooltip(e) {
    const tooltip = document.getElementById('gantt-tooltip');
    if (!tooltip) return;

    tooltip.style.left = (e.clientX + 15) + 'px';
    tooltip.style.top = (e.clientY + 15) + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('gantt-tooltip');
    if (tooltip) {
        tooltip.classList.remove('visible');
    }
}

let currentTaskId = null;

function openTaskModal(taskId) {
    currentTaskId = taskId;
    const modal = document.getElementById('task-modal');
    if (!modal) return;

    const task = tasksData.find(t => t.id === taskId);
    if (!task) return;

    const assignee = typeof usersData !== 'undefined' ?
        usersData.find(u => u.id === task.assignee_id) : null;

    document.getElementById('modal-task-title').textContent = task.title;
    document.getElementById('modal-task-description').textContent = task.description || 'Описание отсутствует';

    const statusEl = document.getElementById('modal-task-status');
    statusEl.textContent = task.status;
    statusEl.className = 'status-badge';
    if (task.status === 'активна') statusEl.classList.add('status-active');
    else if (task.status === 'завершена') statusEl.classList.add('status-completed');
    else statusEl.classList.add('status-paused');

    document.getElementById('modal-task-assignee').textContent = assignee ? assignee.name : 'Не назначен';
    document.getElementById('modal-task-start').textContent = task.start_date || 'Не указана';
    document.getElementById('modal-task-deadline').textContent = task.deadline || 'Не указан';

    loadTaskFiles(taskId);

    const fileUploadSection = document.getElementById('file-upload-section');
    if (fileUploadSection) {
        if (task.status !== 'завершена') {
            fileUploadSection.style.display = 'flex';
        } else {
            fileUploadSection.style.display = 'none';
        }
    }

    modal.classList.add('active');
}

function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    currentTaskId = null;
}

function loadTaskFiles(taskId) {
    const filesContainer = document.getElementById('modal-task-files');
    if (!filesContainer) return;

    // TODO: Backend - Реализовать API endpoint для получения файлов задачи
    // GET /api/tasks/<task_id>/files
    // Ожидаемый ответ: { files: [{ id: string, name: string, url: string, uploaded_at: string }] }

    filesContainer.innerHTML = '<p class="no-data">Файлы не прикреплены (требуется backend)</p>';
}

function uploadTaskFile() {
    const fileInput = document.getElementById('task-file-input');
    if (!fileInput || !fileInput.files.length || !currentTaskId) return;

    const formData = new FormData();
    for (let i = 0; i < fileInput.files.length; i++) {
        formData.append('files', fileInput.files[i]);
    }

    console.log('Uploading files for task:', currentTaskId);

    // TODO: Backend - Реализовать API endpoint для загрузки файлов к задаче
    // POST /api/tasks/<task_id>/files
    // Body: FormData с файлами
    // Ожидаемый ответ: { success: boolean, files: [{ id, name, url }] }
    // Условие: задача не должна быть в статусе "завершена"

    showNotification('Загрузка файлов (требуется backend)', 'success');
    fileInput.value = '';
}

function openChangeAssigneeModal() {
    const modal = document.getElementById('change-assignee-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeChangeAssigneeModal() {
    const modal = document.getElementById('change-assignee-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function changeAssignee() {
    const select = document.getElementById('new-assignee');
    if (!select || !currentTaskId) return;

    const newAssigneeId = select.value;

    console.log('Changing assignee for task:', currentTaskId, 'to:', newAssigneeId);

    // TODO: Backend - Реализовать API endpoint для изменения ответственного
    // PUT /api/tasks/<task_id>/assignee
    // Body: { assignee_id: string }
    // Ожидаемый ответ: { success: boolean, task: Task }

    showNotification('Ответственный изменен (требуется backend)', 'success');
    closeChangeAssigneeModal();
}

function openAddMemberModal() {
    const modal = document.getElementById('add-member-modal');
    if (modal) {
        modal.classList.add('active');
    }
}

function closeAddMemberModal() {
    const modal = document.getElementById('add-member-modal');
    if (modal) {
        modal.classList.remove('active');
    }

    const tokenInput = document.getElementById('member-token');
    if (tokenInput) {
        tokenInput.value = '';
    }
}

function addMemberByToken() {
    const tokenInput = document.getElementById('member-token');
    if (!tokenInput) return;

    const token = tokenInput.value.trim();
    if (!token) {
        showNotification('Введите токен участника', 'error');
        return;
    }

    console.log('Adding member by token:', token, 'to project:', projectId);

     // Отправляем запрос на сервер
    fetch(`/project/${projectId}/add_member_by_token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `token=${encodeURIComponent(token)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            closeAddMemberModal();
            // Перезагружаем страницу для обновления списка участников
            location.reload();
        } else {
            showNotification(data.error || 'Ошибка при добавлении участника', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Ошибка при добавлении участника', 'error');
    });
}


function removeMember(memberId) {
    if (!confirm('Вы уверены, что хотите удалить этого участника из команды?')) {
        return;
    }

    console.log('Removing member:', memberId, 'from project:', projectId);

    // TODO: Backend - Реализовать API endpoint для удаления участника из команды
    // DELETE /api/projects/<project_id>/team/<user_id>
    // Ожидаемый ответ: { success: boolean }
    // Права доступа: куратор или руководитель проекта

    showNotification('Участник удален (требуется backend)', 'success');
}

function showNotification(message, type) {
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }

    const notification = document.createElement('div');
    notification.className = `notification flash ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 3000;
        min-width: 250px;
        animation: slideInRight 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        closeTaskModal();
        closeAddMemberModal();
        closeChangeAssigneeModal();
    }
});

// Дополнительные JS-функции для улучшения функциональности

// Функция для обновления прогресса проекта
function updateProjectProgress(projectId) {
    // TODO: Реализовать обновление прогресса проекта через API
    console.log('Обновление прогресса проекта:', projectId);
}

// Функция для сортировки задач
function sortTasks(sortBy, order = 'asc') {
    const tasksContainer = document.querySelector('.tasks-container');
    if (!tasksContainer) return;

    const tasks = Array.from(tasksContainer.querySelectorAll('.task-item'));
    
    tasks.sort((a, b) => {
        let valA, valB;
        
        switch(sortBy) {
            case 'date':
                valA = new Date(a.dataset.deadline);
                valB = new Date(b.dataset.deadline);
                break;
            case 'priority':
                valA = parseInt(a.dataset.priority) || 0;
                valB = parseInt(b.dataset.priority) || 0;
                break;
            case 'status':
                valA = a.dataset.status || '';
                valB = b.dataset.status || '';
                break;
            default:
                valA = a.querySelector('.task-title')?.textContent || '';
                valB = b.querySelector('.task-title')?.textContent || '';
        }
        
        if (valA < valB) return order === 'asc' ? -1 : 1;
        if (valA > valB) return order === 'asc' ? 1 : -1;
        return 0;
    });
    
    tasks.forEach(task => tasksContainer.appendChild(task));
}

// Функция для фильтрации задач
function filterTasks(status) {
    const tasks = document.querySelectorAll('.task-item');
    
    tasks.forEach(task => {
        if (status === 'all' || task.dataset.status === status) {
            task.style.display = 'block';
        } else {
            task.style.display = 'none';
        }
    });
}

// Функция для поиска задач
function searchTasks(query) {
    const tasks = document.querySelectorAll('.task-item');
    const searchTerm = query.toLowerCase();
    
    tasks.forEach(task => {
        const title = task.querySelector('.task-title')?.textContent.toLowerCase() || '';
        const description = task.querySelector('.task-description')?.textContent.toLowerCase() || '';
        
        if (title.includes(searchTerm) || description.includes(searchTerm)) {
            task.style.display = 'block';
        } else {
            task.style.display = 'none';
        }
    });
}

// Функция для обновления статуса задачи через API
function updateTaskStatus(taskId, newStatus) {
    fetch(`/task/${taskId}/update_status`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `status=${encodeURIComponent(newStatus)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Статус задачи обновлен', 'success');
            // Перезагружаем страницу или обновляем элементы интерфейса
            location.reload();
        } else {
            showNotification('Ошибка при обновлении статуса', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Ошибка при обновлении статуса', 'error');
    });
}

// Функция для добавления задачи
function addTaskToProject(projectId) {
    const title = document.getElementById('new-task-title')?.value;
    const description = document.getElementById('new-task-description')?.value;
    const assignee = document.getElementById('new-task-assignee')?.value;
    const deadline = document.getElementById('new-task-deadline')?.value;
    
    if (!title) {
        showNotification('Укажите название задачи', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    formData.append('assignee_id', assignee);
    formData.append('deadline', deadline);
    
    fetch(`/api/project/${projectId}/tasks`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Задача добавлена', 'success');
            // Очищаем форму
            document.getElementById('new-task-title').value = '';
            document.getElementById('new-task-description').value = '';
            // Перезагружаем страницу
            location.reload();
        } else {
            showNotification(data.message || 'Ошибка при добавлении задачи', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Ошибка при добавлении задачи', 'error');
    });
}

// Функция для инициализации drag and drop для задач
function initDragAndDropTasks() {
    const taskItems = document.querySelectorAll('.task-item');
    
    taskItems.forEach(task => {
        task.draggable = true;
        
        task.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('text/plain', task.dataset.taskId);
            task.classList.add('dragging');
        });
        
        task.addEventListener('dragend', function() {
            task.classList.remove('dragging');
        });
    });
    
    // Обработчики для drop зон
    const dropZones = document.querySelectorAll('.status-column');
    dropZones.forEach(zone => {
        zone.addEventListener('dragover', function(e) {
            e.preventDefault();
            zone.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', function() {
            zone.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', function(e) {
            e.preventDefault();
            zone.classList.remove('drag-over');
            
            const taskId = e.dataTransfer.getData('text/plain');
            const newStatus = zone.dataset.status;
            
            if (taskId && newStatus) {
                updateTaskStatus(taskId, newStatus);
            }
        });
    });
}

// Функция для экспорта данных
function exportProjectData(format) {
    const projectId = document.querySelector('[data-project-id]')?.dataset.projectId;
    if (!projectId) return;
    
    let url;
    switch(format) {
        case 'pdf':
            url = `/project/${projectId}/export/pdf`;
            break;
        case 'excel':
            url = `/project/${projectId}/export/excel`;
            break;
        case 'csv':
            url = `/project/${projectId}/export/csv`;
            break;
        default:
            return;
    }
    
    // Создаем временный элемент для скачивания
    const link = document.createElement('a');
    link.href = url;
    link.download = `project_${projectId}_export.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Функция для инициализации календаря
function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    // Простая реализация календаря
    const today = new Date();
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();
    
    // TODO: Реализовать полнофункциональный календарь с задачами
    console.log('Инициализация календаря', currentYear, currentMonth + 1);
}

// Функция для обновления статистики в реальном времени
function updateRealTimeStats() {
    // TODO: Реализовать WebSocket или периодические запросы для обновления статистики
    console.log('Обновление статистики в реальном времени');
}

// Инициализация дополнительных функций при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализируем drag and drop для задач
    initDragAndDropTasks();
    
    // Инициализируем календарь если он есть на странице
    initCalendar();
    
    // Добавляем обработчики для фильтров
    const statusFilter = document.getElementById('status-filter');
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            filterTasks(this.value);
        });
    }
    
    // Добавляем обработчик для поиска
    const searchInput = document.getElementById('task-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            searchTasks(this.value);
        });
    }
    
    // Добавляем обработчики для сортировки
    const sortSelect = document.getElementById('sort-tasks');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            const [sortBy, order] = this.value.split('-');
            sortTasks(sortBy, order);
        });
    }
});

// Функция для загрузки данных проекта
async function loadProjectData(projectId) {
    try {
        const response = await fetch(`/api/project/${projectId}`);
        if (!response.ok) throw new Error('Network response was not ok');
        
        const projectData = await response.json();
        return projectData;
    } catch (error) {
        console.error('Ошибка загрузки данных проекта:', error);
        return null;
    }
}

// Функция для загрузки задач проекта
async function loadProjectTasks(projectId) {
    try {
        const response = await fetch(`/api/project/${projectId}/tasks`);
        if (!response.ok) throw new Error('Network response was not ok');
        
        const tasks = await response.json();
        return tasks;
    } catch (error) {
        console.error('Ошибка загрузки задач проекта:', error);
        return [];
    }
}

// Функция для обновления представления задач
function updateTasksView(tasks) {
    const container = document.querySelector('.tasks-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    tasks.forEach(task => {
        const taskElement = document.createElement('div');
        taskElement.className = 'task-item';
        taskElement.dataset.taskId = task.id;
        taskElement.dataset.status = task.status;
        taskElement.dataset.deadline = task.deadline;
        
        taskElement.innerHTML = `
            <div class="task-header">
                <h4 class="task-title">${task.title || 'Без названия'}</h4>
                <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span>
            </div>
            <div class="task-body">
                <p class="task-description">${task.description || ''}</p>
                <div class="task-meta">
                    <span class="assignee">${task.assignee_name || 'Не назначен'}</span>
                    <span class="deadline">${task.deadline || 'Без дедлайна'}</span>
                </div>
            </div>
        `;
        
        container.appendChild(taskElement);
    });
}

// Вспомогательная функция для получения класса статуса
function getStatusClass(status) {
    switch(status) {
        case 'активна': return 'status-active';
        case 'завершена': return 'status-completed';
        case 'отложена': return 'status-paused';
        default: return 'status-default';
    }
}

// Функция для валидации форм
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('error');
            isValid = false;
        } else {
            field.classList.remove('error');
        }
    });
    
    return isValid;
}

// Функция для показа прелоадера
function showLoader(show = true) {
    const loader = document.querySelector('.loader') || document.querySelector('.spinner');
    if (loader) {
        loader.style.display = show ? 'block' : 'none';
    }
}

// Функция для форматирования даты
function formatDate(dateString) {
    if (!dateString) return 'Не указана';
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString; // Если формат уже корректный
    
    return date.toLocaleDateString('ru-RU');
}

// Функция для получения относительного времени
function getTimeAgo(dateString) {
    if (!dateString) return 'Не указано';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'сегодня';
    if (diffDays === 1) return 'вчера';
    if (diffDays < 7) return `${diffDays} д. назад`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} нед. назад`;
    return `${Math.floor(diffDays / 30)} мес. назад`;
}
