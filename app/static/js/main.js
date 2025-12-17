document.addEventListener('DOMContentLoaded', function() {
    initMobileMenu();
    initTabs();
    initProjectFilters();
    initTaskFilters();
    initGanttChart();
    initTaskModal();
});

function initMobileMenu() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const nav = document.querySelector('nav');
    
    if (menuToggle && nav) {
        menuToggle.addEventListener('click', function() {
            nav.classList.toggle('active');
            const expanded = nav.classList.contains('active');
            menuToggle.setAttribute('aria-expanded', expanded);
        });
    }
}

function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.dataset.tab;
            
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            this.classList.add('active');
            const targetContent = document.getElementById(targetTab);
            if (targetContent) {
                targetContent.classList.add('active');
            }
            
            if (targetTab === 'gantt-tab') {
                const ganttChart = document.getElementById('gantt-chart');
                if (ganttChart && ganttChart.dataset.projectId) {
                    loadGanttData(ganttChart.dataset.projectId);
                }
            }
        });
    });
}

function initProjectFilters() {
    const showCompletedCheckbox = document.getElementById('show-completed-projects');
    const projectsList = document.getElementById('projects-list');
    
    if (showCompletedCheckbox && projectsList) {
        showCompletedCheckbox.addEventListener('change', function() {
            const showCompleted = this.checked;
            const projectCards = projectsList.querySelectorAll('.project-card');
            
            projectCards.forEach(card => {
                const status = card.dataset.status;
                if (status === 'завершен') {
                    card.style.display = showCompleted ? '' : 'none';
                }
            });
        });
        
        showCompletedCheckbox.dispatchEvent(new Event('change'));
    }
}

function initTaskFilters() {
    const projectFilter = document.getElementById('task-project-filter');
    const statusFilter = document.getElementById('task-status-filter');
    const tasksList = document.getElementById('tasks-list');
    
    if (tasksList) {
        function filterTasks() {
            const projectId = projectFilter ? projectFilter.value : '';
            const status = statusFilter ? statusFilter.value : '';
            const taskCards = tasksList.querySelectorAll('.task-card');
            
            taskCards.forEach(card => {
                const cardProjectId = card.dataset.projectId;
                const cardStatus = card.dataset.status;
                
                let showByProject = !projectId || cardProjectId === projectId;
                let showByStatus = !status || cardStatus === status;
                
                card.style.display = (showByProject && showByStatus) ? '' : 'none';
            });
        }
        
        if (projectFilter) {
            projectFilter.addEventListener('change', filterTasks);
        }
        if (statusFilter) {
            statusFilter.addEventListener('change', filterTasks);
        }
    }
}

let currentZoom = 'week';
let ganttTasks = [];

function initGanttChart() {
    const ganttContainer = document.getElementById('gantt-chart');
    const zoomButtons = document.querySelectorAll('.gantt-zoom-btn');
    
    if (!ganttContainer) return;
    
    zoomButtons.forEach(button => {
        button.addEventListener('click', function() {
            zoomButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            currentZoom = this.dataset.zoom;
            
            if (ganttContainer.dataset.projectId) {
                renderGantt();
            }
        });
    });
}

function loadGanttData(projectId) {
    fetch(`/api/project/${projectId}/tasks`)
        .then(response => response.json())
        .then(tasks => {
            ganttTasks = tasks;
            renderGantt();
        })
        .catch(error => {
            console.error('Error loading tasks:', error);
        });
}

function parseDate(dateStr) {
    if (!dateStr) return null;
    
    if (dateStr.includes('-')) {
        return new Date(dateStr);
    }
    
    if (dateStr.includes('/')) {
        const parts = dateStr.split('/');
        if (parts.length === 3) {
            return new Date(parts[2], parts[1] - 1, parts[0]);
        }
    }
    
    if (dateStr.includes('.')) {
        const parts = dateStr.split('.');
        if (parts.length === 3) {
            return new Date(parts[2], parts[1] - 1, parts[0]);
        }
    }
    
    return new Date(dateStr);
}

function formatDateDDMMYYYY(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function renderGantt() {
    const ganttChart = document.getElementById('gantt-chart');
    if (!ganttChart || ganttTasks.length === 0) {
        ganttChart.innerHTML = '<p class="no-data">Нет задач для отображения</p>';
        return;
    }
    
    let minDate = null;
    let maxDate = null;
    
    ganttTasks.forEach(task => {
        const startDate = parseDate(task.start_date) || parseDate(task.created_at);
        const endDate = parseDate(task.deadline);
        
        if (startDate && (!minDate || startDate < minDate)) {
            minDate = new Date(startDate);
        }
        if (endDate && (!maxDate || endDate > maxDate)) {
            maxDate = new Date(endDate);
        }
    });
    
    if (!minDate || !maxDate) {
        ganttChart.innerHTML = '<p class="no-data">Недостаточно данных для диаграммы</p>';
        return;
    }
    
    minDate.setDate(minDate.getDate() - 3);
    maxDate.setDate(maxDate.getDate() + 7);
    
    let cellWidth, dateFormat;
    switch (currentZoom) {
        case 'day':
            cellWidth = 40;
            dateFormat = 'day';
            break;
        case 'week':
            cellWidth = 35;
            dateFormat = 'day';
            break;
        case 'month':
            cellWidth = 20;
            dateFormat = 'day';
            break;
        case 'year':
            cellWidth = 60;
            dateFormat = 'month';
            break;
        default:
            cellWidth = 35;
            dateFormat = 'day';
    }
    
    let timelineItems = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    if (currentZoom === 'year') {
        const startMonth = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
        const endMonth = new Date(maxDate.getFullYear(), maxDate.getMonth() + 1, 0);
        
        let currentMonth = new Date(startMonth);
        while (currentMonth <= endMonth) {
            const isCurrentMonth = currentMonth.getMonth() === today.getMonth() && 
                                  currentMonth.getFullYear() === today.getFullYear();
            timelineItems.push({
                date: new Date(currentMonth),
                label: currentMonth.toLocaleDateString('ru-RU', { month: 'short' }),
                isToday: isCurrentMonth,
                isWeekend: false
            });
            currentMonth.setMonth(currentMonth.getMonth() + 1);
        }
    } else {
        let currentDate = new Date(minDate);
        while (currentDate <= maxDate) {
            const dayOfWeek = currentDate.getDay();
            const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
            const isToday = currentDate.getTime() === today.getTime();
            
            timelineItems.push({
                date: new Date(currentDate),
                label: currentDate.getDate(),
                isToday: isToday,
                isWeekend: isWeekend
            });
            currentDate.setDate(currentDate.getDate() + 1);
        }
    }
    
    let html = '<div class="gantt-timeline">';
    html += `<div class="gantt-task-label" style="min-width: 160px; border-right: 2px solid var(--gray-300);">Задача</div>`;
    
    timelineItems.forEach(item => {
        let classes = 'gantt-timeline-item';
        if (item.isToday) classes += ' today';
        if (item.isWeekend) classes += ' weekend';
        html += `<div class="${classes}" style="min-width: ${cellWidth}px;">${item.label}</div>`;
    });
    html += '</div>';
    
    html += '<div class="gantt-tasks">';
    
    ganttTasks.forEach(task => {
        const startDate = parseDate(task.start_date) || parseDate(task.created_at);
        const endDate = parseDate(task.deadline);
        
        if (!startDate || !endDate) return;
        
        let statusClass = 'status-active';
        if (task.status === 'завершена') statusClass = 'status-completed';
        else if (task.status === 'отложена') statusClass = 'status-paused';
        
        let startOffset, barWidth;
        
        if (currentZoom === 'year') {
            const startMonthDiff = (startDate.getFullYear() - minDate.getFullYear()) * 12 + 
                                  (startDate.getMonth() - minDate.getMonth());
            const endMonthDiff = (endDate.getFullYear() - minDate.getFullYear()) * 12 + 
                                (endDate.getMonth() - minDate.getMonth());
            startOffset = startMonthDiff * cellWidth;
            barWidth = Math.max((endMonthDiff - startMonthDiff + 1) * cellWidth, cellWidth);
        } else {
            const startDaysDiff = Math.floor((startDate - minDate) / (1000 * 60 * 60 * 24));
            const endDaysDiff = Math.floor((endDate - minDate) / (1000 * 60 * 60 * 24));
            startOffset = startDaysDiff * cellWidth;
            barWidth = Math.max((endDaysDiff - startDaysDiff + 1) * cellWidth, cellWidth);
        }
        
        const assigneeName = task.assignee_name || 'Не назначен';
        
        html += `
            <div class="gantt-row">
                <div class="gantt-task-label" title="${task.title}">${task.title}</div>
                <div class="gantt-task-bar-container">
                    <div class="gantt-task-bar ${statusClass}" 
                         style="left: ${startOffset}px; width: ${barWidth}px;"
                         data-task-id="${task.id}"
                         title="${task.title} - ${assigneeName}">
                        ${assigneeName}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    
    ganttChart.innerHTML = html;
    
    ganttChart.querySelectorAll('.gantt-task-bar').forEach(bar => {
        bar.addEventListener('click', function() {
            const taskId = this.dataset.taskId;
            openTaskModal(taskId);
        });
    });
}

function initTaskModal() {
    const modal = document.getElementById('task-modal');
    if (!modal) return;
    
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-btn');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', closeTaskModal);
    });
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeTaskModal();
        }
    });
    
    const editButtons = document.querySelectorAll('.edit-task-btn');
    editButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            openTaskModal(this.dataset.taskId);
        });
    });
    
    const taskRows = document.querySelectorAll('.task-row');
    taskRows.forEach(row => {
        row.addEventListener('click', function(e) {
            if (!e.target.closest('button') && !e.target.closest('a')) {
                openTaskModal(this.dataset.taskId);
            }
        });
    });
    
    const editForm = document.getElementById('edit-task-form');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitTaskEdit();
        });
    }
}

function openTaskModal(taskId) {
    const modal = document.getElementById('task-modal');
    if (!modal) return;
    
    fetch(`/api/task/${taskId}`)
        .then(response => response.json())
        .then(task => {
            document.getElementById('edit-task-id').value = task.id;
            document.getElementById('edit-task-title').value = task.title || '';
            document.getElementById('edit-task-description').value = task.description || '';
            document.getElementById('edit-task-status').value = task.status || 'активна';
            
            const startDate = parseDate(task.start_date);
            const deadline = parseDate(task.deadline);
            
            if (startDate) {
                document.getElementById('edit-task-start').value = formatDateForInput(startDate);
            }
            if (deadline) {
                document.getElementById('edit-task-deadline').value = formatDateForInput(deadline);
            }
            
            const assigneeSelect = document.getElementById('edit-task-assignee');
            assigneeSelect.innerHTML = '';
            
            if (task.team_users && task.team_users.length > 0) {
                task.team_users.forEach(user => {
                    const option = document.createElement('option');
                    option.value = user.id;
                    option.textContent = user.name;
                    if (user.id === task.assignee_id) {
                        option.selected = true;
                    }
                    assigneeSelect.appendChild(option);
                });
            }
            
            const historyList = modal.querySelector('.history-list');
            if (historyList && task.history) {
                historyList.innerHTML = '';
                task.history.forEach(entry => {
                    historyList.innerHTML += `
                        <div class="history-item">
                            <strong>${entry.action}</strong>
                            <span class="history-date">${entry.date} - ${entry.user_name}</span>
                        </div>
                    `;
                });
            }
            
            const reportsList = modal.querySelector('.reports-list');
            if (reportsList && task.reports) {
                reportsList.innerHTML = '';
                task.reports.forEach(report => {
                    let fileHtml = '';
                    if (report.file_info) {
                        const fileName = report.file_info.filename;
                        const filePath = report.file_info.path;
                        const fileUrl = `/uploads/${filePath}`;
                        fileHtml = `
                            <div class="report-file">
                                <a href="${fileUrl}" target="_blank" class="file-link">
                                    📎 ${fileName}
                                </a>
                            </div>
                        `;
                    }
                    
                    reportsList.innerHTML += `
                        <div class="report-item">
                            <span class="report-comment">${report.comment || 'Без комментария'}</span>
                            <span class="report-date">
                                <span>${report.date}</span>
                                <span>${report.executor_name}</span>
                            </span>
                            ${fileHtml}
                        </div>
                    `;
                });
            }
            
            modal.classList.add('active');
        })
        .catch(error => {
            console.error('Error loading task:', error);
            alert('Ошибка при загрузке задачи');
        });
}

function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function formatDateForInput(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

function submitTaskEdit() {
    const taskId = document.getElementById('edit-task-id').value;
    const formData = new FormData();
    
    formData.append('title', document.getElementById('edit-task-title').value);
    formData.append('description', document.getElementById('edit-task-description').value);
    formData.append('assignee_id', document.getElementById('edit-task-assignee').value);
    formData.append('status', document.getElementById('edit-task-status').value);
    formData.append('start_date', document.getElementById('edit-task-start').value);
    formData.append('deadline', document.getElementById('edit-task-deadline').value);
    
    fetch(`/task/${taskId}/update`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            closeTaskModal();
            location.reload();
        } else {
            alert(data.error || 'Ошибка при сохранении');
        }
    })
    .catch(error => {
        console.error('Error updating task:', error);
        alert('Ошибка при сохранении задачи');
    });
}
