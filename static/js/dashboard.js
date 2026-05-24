// Dashboard and Telemetry Charts Logic
let frenzyChart = null;
let waterChart = null;

// Color Constants for charts
const COLOR_ACCENT = '#00f5c4';
const COLOR_PRIMARY = '#3b82f6';
const COLOR_DANGER = '#ef4444';
const COLOR_OPTIMAL = '#10b981';

// Fetch telemetry data from local SQLite database
async function fetchTelemetry() {
    try {
        const response = await fetch('/api/telemetry');
        const data = await response.json();
        
        if (data && data.length > 0) {
            updateDashboardKPIs(data);
            renderCharts(data);
            populateLogTable(data);
        }
    } catch (error) {
        console.error("Error al obtener la telemetría:", error);
    }
}

// Update the Top KPI cards based on the latest database entries
function updateDashboardKPIs(telemetryList) {
    const latest = telemetryList[telemetryList.length - 1];
    
    // 1. Biological Status
    const statusVal = document.getElementById('kpi-status-value');
    const statusDesc = document.getElementById('kpi-status-desc');
    const statusCard = document.getElementById('kpi-status-card');
    const statusIcon = statusCard.querySelector('.kpi-icon');
    
    statusVal.textContent = latest.comfort_status.toUpperCase();
    statusIcon.className = 'kpi-icon'; // reset
    
    if (latest.comfort_status === 'Optimal') {
        statusVal.textContent = 'ÓPTIMO';
        statusVal.style.color = COLOR_OPTIMAL;
        statusDesc.textContent = 'Condiciones biológicas estables';
        statusIcon.classList.add('status-optimal');
    } else if (latest.comfort_status === 'Stress') {
        statusVal.textContent = 'ESTRÉS';
        statusVal.style.color = '#f59e0b';
        statusDesc.textContent = latest.notes || 'Peces inactivos o clima fuera de rango';
        statusIcon.classList.add('status-stress');
    } else {
        statusVal.textContent = 'PELIGRO';
        statusVal.style.color = COLOR_DANGER;
        statusDesc.textContent = 'Alerta crítica de oxígeno o temperatura';
        statusIcon.classList.add('status-danger');
    }
    
    // 2. Fish Count (Average of last 5 entries)
    const last5 = telemetryList.slice(-5);
    const avgFish = Math.round(last5.reduce((sum, item) => sum + item.fish_count, 0) / last5.length);
    document.getElementById('kpi-fish-value').textContent = `${avgFish} uds`;
    
    // 3. Feeding intensity efficiency
    // Calculate total feeding events in the 48h period and avg intensity
    const feedingEventItems = telemetryList.filter(item => item.feeding_events === 1);
    const avgIntensity = feedingEventItems.length > 0 
        ? Math.round(feedingEventItems.reduce((sum, item) => sum + item.feeding_intensity, 0) / feedingEventItems.length)
        : 0;
    
    document.getElementById('kpi-frenzy-value').textContent = `${avgIntensity}%`;
    
    // 4. Water Quality
    document.getElementById('kpi-water-value').textContent = `${latest.water_temperature}°C | ${latest.dissolved_oxygen} ppm`;
    document.getElementById('kpi-water-desc').textContent = `pH del estanque: ${latest.ph_level} (Normal)`;
}

// Populate the bottom logging table
function populateLogTable(telemetryList) {
    const tbody = document.getElementById('telemetry-table-body');
    tbody.innerHTML = '';
    
    // Render in reverse chronological order (latest first)
    const reversed = [...telemetryList].reverse();
    
    reversed.forEach(row => {
        const tr = document.createElement('tr');
        
        // Format timestamp
        const date = new Date(row.timestamp);
        const dateStr = date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' }) + ' ' + 
                      date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        
        // Feeding event text
        const feedingText = row.feeding_events === 1 
            ? '<span class="status-pill optimal">Alimentado (Frenesí)</span>' 
            : '<span class="status-pill" style="background:rgba(255,255,255,0.03);color:#9ca3af;">N/A</span>';
            
        // Comfort pill
        let comfortPill = '';
        if (row.comfort_status === 'Optimal') {
            comfortPill = '<span class="status-pill optimal">Óptimo</span>';
        } else if (row.comfort_status === 'Stress') {
            comfortPill = '<span class="status-pill stress">Estrés</span>';
        } else {
            comfortPill = '<span class="status-pill danger">Peligro</span>';
        }
        
        const sickText = row.sick_fish_count > 0 
            ? ` <span style="color:var(--color-danger);font-weight:600;">(${row.sick_fish_count} enf.)</span>` 
            : '';
        
        tr.innerHTML = `
            <td style="font-weight: 500;">${dateStr}</td>
            <td>${row.fish_count} peces${sickText}</td>
            <td style="font-weight: 600; color: ${row.feeding_intensity > 50 ? COLOR_ACCENT : '#fff'}">${row.feeding_intensity.toFixed(1)}%</td>
            <td>${feedingText}</td>
            <td>${row.water_temperature}°C | DO: ${row.dissolved_oxygen} | pH: ${row.ph_level}</td>
            <td>${comfortPill}</td>
            <td style="color: #9ca3af; font-size: 0.8rem;">${row.notes || '-'}</td>
        `;
        
        tbody.appendChild(tr);
    });
}

// Render professional Chart.js graphs
function renderCharts(telemetryList) {
    const labels = telemetryList.map(item => {
        const date = new Date(item.timestamp);
        return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    });
    
    const turbulenceData = telemetryList.map(item => item.feeding_intensity);
    const feedingEvents = telemetryList.map(item => item.feeding_events * 50); // Scale up for visual representation on same axes
    
    const tempValues = telemetryList.map(item => item.water_temperature);
    const oxygenValues = telemetryList.map(item => item.dissolved_oxygen);
    const phValues = telemetryList.map(item => item.ph_level);

    // 1. Frenzy / Turbulence Chart
    if (frenzyChart) {
        frenzyChart.destroy();
    }
    
    const ctxFrenzy = document.getElementById('frenzyChart').getContext('2d');
    
    // Create gradient fill for turbulence area
    const gradAccent = ctxFrenzy.createLinearGradient(0, 0, 0, 250);
    gradAccent.addColorStop(0, 'rgba(0, 245, 196, 0.25)');
    gradAccent.addColorStop(1, 'rgba(0, 245, 196, 0.0)');
    
    frenzyChart = new Chart(ctxFrenzy, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Índice de Turbulencia %',
                    data: turbulenceData,
                    borderColor: COLOR_ACCENT,
                    backgroundColor: gradAccent,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Evento de Alimentación (Trigger)',
                    data: feedingEvents,
                    type: 'bar',
                    backgroundColor: 'rgba(59, 130, 246, 0.25)',
                    borderColor: COLOR_PRIMARY,
                    borderWidth: 1,
                    barThickness: 8,
                    borderRadius: 4,
                    yAxisID: 'y'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#9ca3af',
                        font: { family: 'Outfit', size: 11 }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#6b7280', font: { family: 'Outfit', size: 10 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#6b7280', font: { family: 'Outfit', size: 10 } },
                    min: 0,
                    max: 100
                }
            }
        }
    });

    // 2. Water / Biology parameters Chart
    if (waterChart) {
        waterChart.destroy();
    }
    
    const ctxWater = document.getElementById('waterChart').getContext('2d');
    
    waterChart = new Chart(ctxWater, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Temperatura (°C)',
                    data: tempValues,
                    borderColor: '#f59e0b',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'yTemp'
                },
                {
                    label: 'Oxígeno (ppm)',
                    data: oxygenValues,
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'yO2'
                },
                {
                    label: 'pH',
                    data: phValues,
                    borderColor: '#a855f7',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    yAxisID: 'yPH'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#9ca3af',
                        font: { family: 'Outfit', size: 11 }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#6b7280', font: { family: 'Outfit', size: 10 } }
                },
                yTemp: {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.04)' },
                    ticks: { color: '#f59e0b', font: { family: 'Outfit', size: 10 } },
                    min: 20,
                    max: 35,
                    title: { display: true, text: 'Temp (°C)', color: '#f59e0b', font: { family: 'Outfit' } }
                },
                yO2: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false }, // Only show grid of left axis
                    ticks: { color: '#3b82f6', font: { family: 'Outfit', size: 10 } },
                    min: 2,
                    max: 8,
                    title: { display: true, text: 'DO (ppm)', color: '#3b82f6', font: { family: 'Outfit' } }
                },
                yPH: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#a855f7', font: { family: 'Outfit', size: 10 } },
                    min: 5.5,
                    max: 9.5,
                    title: { display: true, text: 'pH', color: '#a855f7', font: { family: 'Outfit' } }
                }
            }
        }
    });
}

// Alert System Logic (Read/Unread persistency)
let readAlerts = JSON.parse(localStorage.getItem('read_alerts') || '[]');

function initAlertSystem(telemetryList) {
    // Filter out rows that represent stress or danger states
    const anomalies = telemetryList.filter(row => row.comfort_status !== 'Optimal');
    
    // Sort anomalies chronologically in descending order (newest first)
    const activeAlerts = [...anomalies].reverse();
    
    updateAlertBadge(activeAlerts);
    renderAlertList(activeAlerts);
    checkNewCriticalAlerts(activeAlerts);
}

function updateAlertBadge(activeAlerts) {
    const unreadAlerts = activeAlerts.filter(a => !readAlerts.includes(a.id));
    const badge = document.getElementById('bell-badge');
    
    if (unreadAlerts.length > 0) {
        badge.textContent = unreadAlerts.length;
        badge.style.display = 'flex';
        // Add a soft pulsing glow to the bell button if there are unread alerts
        document.getElementById('btn-bell').style.boxShadow = '0 0 12px rgba(239, 68, 68, 0.4)';
    } else {
        badge.style.display = 'none';
        document.getElementById('btn-bell').style.boxShadow = 'none';
    }
}

function renderAlertList(activeAlerts) {
    const list = document.getElementById('dropdown-alerts-list');
    list.innerHTML = '';
    
    if (activeAlerts.length === 0) {
        list.innerHTML = '<div style="color:#6b7280;text-align:center;padding:24px;font-size:0.75rem;">Sin alertas en el estanque.</div>';
        return;
    }
    
    activeAlerts.forEach(alert => {
        const isUnread = !readAlerts.includes(alert.id);
        const div = document.createElement('div');
        const severityClass = alert.comfort_status.toLowerCase(); // 'danger' or 'stress'
        
        div.className = `alert-item ${severityClass} ${isUnread ? 'unread' : ''}`;
        
        const date = new Date(alert.timestamp);
        const timeStr = date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' }) + ' ' + 
                        date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        
        const title = alert.comfort_status === 'Danger' ? '¡ALERTA CRÍTICA!' : 'ADVERTENCIA';
        
        div.innerHTML = `
            <div class="alert-header">
                <span class="alert-title" style="color: ${alert.comfort_status === 'Danger' ? COLOR_DANGER : '#f59e0b'};">${title}</span>
            </div>
            <p class="alert-desc">${alert.notes || 'Parámetros ambientales fuera del límite de confort'}</p>
            <p class="alert-desc" style="font-size:0.7rem;opacity:0.7;margin-top:2px;">Temp: ${alert.water_temperature}°C | Oxígeno: ${alert.dissolved_oxygen} ppm | pH: ${alert.ph_level}</p>
            <span class="alert-time">${timeStr}</span>
        `;
        
        list.appendChild(div);
    });
}

function checkNewCriticalAlerts(activeAlerts) {
    if (activeAlerts.length === 0) return;
    
    const latest = activeAlerts[0];
    const isUnread = !readAlerts.includes(latest.id);
    
    // If the latest alert is unread and is from the last 2 minutes, show the big system banner
    const alertTime = new Date(latest.timestamp).getTime();
    const timeDiffMinutes = (Date.now() - alertTime) / 60000;
    
    if (isUnread && timeDiffMinutes < 5) {
        showSystemAlertBanner(latest);
    }
}

function showSystemAlertBanner(alert) {
    // Check if banner already exists
    let banner = document.getElementById('system-alert-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'system-alert-banner';
        banner.className = 'system-alert-banner';
        document.body.appendChild(banner);
    }
    
    const isDanger = alert.comfort_status === 'Danger';
    const bgColor = isDanger ? 'rgba(239, 68, 68, 0.95)' : 'rgba(245, 158, 11, 0.95)';
    const shadowColor = isDanger ? 'rgba(239, 68, 68, 0.4)' : 'rgba(245, 158, 11, 0.4)';
    
    banner.style.background = bgColor;
    banner.style.boxShadow = `0 20px 50px ${shadowColor}`;
    
    banner.innerHTML = `
        <div class="system-alert-icon">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"></path></svg>
        </div>
        <div class="system-alert-content">
            <h4>${isDanger ? '¡ALERTA CRÍTICA EN EL ESTANQUE!' : 'ADVERTENCIA BIOLÓGICA'}</h4>
            <p>${alert.notes || 'Se ha detectado una variable fuera de la zona de confort de las tilapias.'}</p>
            <p style="font-size:0.75rem;margin-top:4px;opacity:0.9;">Detalles: Temp: ${alert.water_temperature}°C | Oxígeno: ${alert.dissolved_oxygen} ppm | pH: ${alert.ph_level}</p>
        </div>
        <button class="system-alert-close" onclick="closeSystemAlertBanner(${alert.id})">
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
    `;
    
    // Slide down after a tiny delay
    setTimeout(() => {
        banner.classList.add('show');
    }, 100);
}

window.closeSystemAlertBanner = function(alertId) {
    const banner = document.getElementById('system-alert-banner');
    if (banner) {
        banner.classList.remove('show');
    }
    // Mark as read so it doesn't show up again
    if (alertId && !readAlerts.includes(alertId)) {
        readAlerts.push(alertId);
        localStorage.setItem('read_alerts', JSON.stringify(readAlerts));
        // Refresh UI
        fetchTelemetry();
    }
}

// Initialise Dashboard listeners
document.addEventListener('DOMContentLoaded', () => {
    fetchTelemetry();
    
    // Auto refresh telemetry data every 60 seconds
    setInterval(fetchTelemetry, 60000);
    
    document.getElementById('btn-refresh-telemetry').addEventListener('click', () => {
        fetchTelemetry();
        window.showToast("Datos de la base de datos actualizados.");
    });
    
    // Toggle Alerts Dropdown
    const btnBell = document.getElementById('btn-bell');
    const dropdown = document.getElementById('notification-dropdown');
    
    btnBell.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdown.classList.toggle('show');
    });
    
    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && e.target !== btnBell) {
            dropdown.classList.remove('show');
        }
    });
    
    // Clear / read alerts button action
    document.getElementById('btn-clear-alerts').addEventListener('click', () => {
        // Fetch all current anomalies from UI list items to mark them as read
        const items = document.querySelectorAll('#dropdown-alerts-list .alert-item');
        if (items.length === 0) return;
        
        // Push all unread alerts to read memory
        const anomalies = window.latestTelemetryData ? window.latestTelemetryData.filter(row => row.comfort_status !== 'Optimal') : [];
        anomalies.forEach(a => {
            if (!readAlerts.includes(a.id)) {
                readAlerts.push(a.id);
            }
        });
        
        localStorage.setItem('read_alerts', JSON.stringify(readAlerts));
        updateAlertBadge([]);
        
        // Visual updates
        document.querySelectorAll('#dropdown-alerts-list .alert-item').forEach(item => {
            item.classList.remove('unread');
        });
        
        window.showToast("Alertas marcadas como leídas.");
        
        // Hide badge
        document.getElementById('bell-badge').style.display = 'none';
        btnBell.style.boxShadow = 'none';
    });
});

// Wrap fetchTelemetry to feed alert system
const originalFetchTelemetry = fetchTelemetry;
fetchTelemetry = async function() {
    try {
        const response = await fetch('/api/telemetry');
        const data = await response.json();
        
        if (data && data.length > 0) {
            window.latestTelemetryData = data; // store in window for reference
            updateDashboardKPIs(data);
            renderCharts(data);
            populateLogTable(data);
            initAlertSystem(data); // Process alerts
        }
    } catch (error) {
        console.error("Error al obtener la telemetría:", error);
    }
}

// Export to window for tab switching hook
window.fetchTelemetry = fetchTelemetry;
