// Video Upload and Configuration Settings Logic
document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    loadVideos();
    initSettingsForm();
    
    // Simulate feeding button listener
    document.getElementById('btn-process-demo').addEventListener('click', triggerDemoSimulation);
});

// 1. Drag & Drop File Upload Management
function initUploadZone() {
    const dropZone = document.getElementById('drop-zone');
    const videoInput = document.getElementById('video-input');
    
    // Click to upload
    dropZone.addEventListener('click', () => videoInput.click());
    
    videoInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFileUpload(file);
    });
    
    // Drag and drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        }, false);
    });
    
    dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) {
            handleFileUpload(file);
        } else {
            window.showToast("Por favor carga un archivo de video válido.", "error");
        }
    });
}

// Upload file to Flask server
async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('video', file);
    
    window.showToast("Subiendo video... Por favor espera.");
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (result.status === 'success') {
            window.showToast("Carga exitosa. Iniciando procesamiento de visión.");
            loadVideos(); // Reload list to show the new item
            trackVideoProgress(result.video_id);
        } else {
            window.showToast(result.error || "Error al subir el video.", "error");
        }
    } catch (error) {
        console.error("Error subiendo el video:", error);
        window.showToast("Error de conexión con el servidor local.", "error");
    }
}

// 2. Queue List and Polling Status
async function loadVideos() {
    try {
        const response = await fetch('/api/videos');
        const videos = await response.json();
        
        const listContainer = document.getElementById('video-list-container');
        listContainer.innerHTML = '';
        
        if (videos.length === 0) {
            listContainer.innerHTML = '<div style="color: #6b7280; text-align: center; padding: 20px; font-size: 0.85rem;">No hay videos cargados aún.</div>';
            return;
        }
        
        videos.forEach(video => {
            const div = document.createElement('div');
            div.className = 'video-item';
            div.dataset.id = video.id;
            
            // Format time
            const date = new Date(video.upload_time);
            const timeStr = date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' }) + ' ' + 
                            date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
            
            let badgeClass = video.status;
            let badgeText = video.status === 'completed' ? 'Completado' : 
                            video.status === 'processing' ? 'Procesando' : 
                            video.status === 'uploaded' ? 'En cola' : 'Fallido';
            
            let progressHtml = '';
            if (video.status === 'processing' || video.status === 'uploaded') {
                progressHtml = `
                    <div class="progress-container">
                        <div class="progress-bar" id="progress-bar-${video.id}" style="width: 0%;"></div>
                    </div>
                `;
                // Start polling if not already tracking
                trackVideoProgress(video.id);
            }
            
            div.innerHTML = `
                <div class="video-info">
                    <span class="video-name">${video.filename.split('_').slice(2).join('_') || video.filename}</span>
                    <span class="video-time">Cargado: ${timeStr}</span>
                    ${progressHtml}
                </div>
                <span class="video-badge ${badgeClass}">${badgeText}</span>
            `;
            
            // On click list item, display video
            if (video.status === 'completed') {
                div.addEventListener('click', () => selectVideo(video));
            } else if (video.status === 'failed') {
                div.addEventListener('click', () => {
                    window.showToast("El procesamiento de este video falló.", "error");
                });
            } else {
                div.addEventListener('click', () => {
                    window.showToast("El video se está procesando. Por favor espera.", "error");
                });
            }
            
            listContainer.appendChild(div);
        });
    } catch (error) {
        console.error("Error cargando la lista de videos:", error);
    }
}

// Poll status of an active video job
const activePolls = new Set();
function trackVideoProgress(videoId) {
    if (activePolls.has(videoId)) return;
    activePolls.add(videoId);
    
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${videoId}`);
            const data = await response.json();
            
            const progressBar = document.getElementById(`progress-bar-${videoId}`);
            if (progressBar) {
                progressBar.style.width = `${data.progress}%`;
            }
            
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(interval);
                activePolls.delete(videoId);
                loadVideos(); // Reload list to update badges
                
                if (data.status === 'completed') {
                    window.showToast("Procesamiento de video finalizado con éxito.");
                    // Refresh main dashboard metrics too
                    if (window.fetchTelemetry) window.fetchTelemetry();
                } else {
                    window.showToast("Error al procesar el video con visión por computador.", "error");
                }
            }
        } catch (error) {
            console.error("Error polling video status:", error);
            clearInterval(interval);
            activePolls.delete(videoId);
        }
    }, 1500);
}

// 3. Play Video & Load stats details
function selectVideo(video) {
    // Highlight selected item in list
    document.querySelectorAll('.video-item').forEach(item => {
        item.classList.remove('active');
        if (parseInt(item.dataset.id) === video.id) item.classList.add('active');
    });

    const placeholder = document.getElementById('player-placeholder');
    const wrapper = document.getElementById('video-wrapper');
    const player = document.getElementById('processed-video-player');
    const metaContainer = document.getElementById('player-metadata');
    const nameBadge = document.getElementById('selected-video-name');
    
    nameBadge.textContent = video.filename.split('_').slice(2).join('_') || video.filename;
    
    placeholder.style.display = 'none';
    wrapper.style.display = 'block';
    metaContainer.style.display = 'block';
    
    // Load source
    player.src = `/processed/${video.processed_filename}`;
    player.load();
    
    // Load metadata statistics
    document.getElementById('meta-fish').textContent = `${video.fish_count_average} peces`;
    document.getElementById('meta-turb-avg').textContent = `${video.turbulence_average.toFixed(1)}%`;
    
    // Simulated peak / frenzy metrics computed during processor
    document.getElementById('meta-turb-max').textContent = `${(video.turbulence_average * 1.5).toFixed(1)}%`;
    
    const frenzyDuration = Math.round(video.duration * 0.4); // Approx duration
    document.getElementById('meta-frenzy-duration').textContent = `${frenzyDuration} segundos`;
    document.getElementById('meta-lethargic').textContent = `${video.fish_lethargic_max || 0} peces`;
    document.getElementById('meta-erratic').textContent = `${video.fish_erratic_max || 0} peces`;
}

// 4. Settings Form Management
function initSettingsForm() {
    const form = document.getElementById('settings-form');
    
    // Load values
    loadSettings();
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });
        
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            
            if (result.status === 'success') {
                window.showToast("Configuración guardada correctamente en el nodo local.");
            } else {
                window.showToast("Error al guardar la configuración.", "error");
            }
        } catch (error) {
            console.error("Error guardando settings:", error);
            window.showToast("Error de conexión al guardar.", "error");
        }
    });
}

async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        
        for (const [key, value] of Object.entries(settings)) {
            const input = document.getElementById(key);
            if (input) input.value = value;
        }
    } catch (error) {
        console.error("Error al cargar settings:", error);
    }
}

// 5. Trigger synthetic feeding demo
async function triggerDemoSimulation() {
    window.showToast("Iniciando simulación sintética de alimentación...");
    try {
        const response = await fetch('/api/process_demo', {
            method: 'POST'
        });
        const result = await response.json();
        
        if (result.status === 'success') {
            window.showToast("Simulación iniciada. Procesando video sintético en cola...");
            loadVideos();
            trackVideoProgress(result.video_id);
            
            // Switch view to videos tab to let user see progress
            document.querySelector('[data-tab="vision-tab"]').click();
        } else {
            window.showToast("Error al iniciar la simulación.", "error");
        }
    } catch (error) {
        console.error("Error al gatillar simulación de demo:", error);
        window.showToast("Error al conectar con la API de simulación.", "error");
    }
}

// Export functions to window
window.loadVideos = loadVideos;
window.loadSettings = loadSettings;
