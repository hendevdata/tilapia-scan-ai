from flask import Flask, request, jsonify, render_template, send_from_directory, url_for
import os
import threading
import sqlite3
from datetime import datetime, timedelta
import database
import cv_processor

app = Flask(__name__)

# Configure upload and processed directories
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
PROCESSED_FOLDER = os.path.join(os.path.dirname(__file__), 'processed')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Global dictionary to track video processing progress
processing_progress = {}

# Initialize database
database.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/processed/<filename>')
def serve_processed(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        data = request.json
        database.update_settings(data)
        return jsonify({"status": "success", "message": "Configuración guardada correctamente."})
    else:
        return jsonify(database.get_settings())

@app.route('/api/videos', methods=['GET'])
def api_videos():
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos ORDER BY id DESC")
    videos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(videos)

@app.route('/api/status/<int:video_id>', methods=['GET'])
def api_status(video_id):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, processed_filename FROM videos WHERE id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Video no encontrado"}), 404
        
    status = row['status']
    progress = processing_progress.get(video_id, 0)
    
    if status == 'completed':
        progress = 100
        
    return jsonify({
        "video_id": video_id,
        "status": status,
        "progress": progress,
        "processed_filename": row['processed_filename']
    })

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"error": "No se envió ningún archivo de video"}), 400
        
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400
        
    if file:
        # Create safe filename
        filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Save to database with 'uploaded' status
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO videos (filename, upload_time, status)
            VALUES (?, ?, ?)
        ''', (filename, datetime.now().isoformat(), 'uploaded'))
        video_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Start background processing thread
        processing_progress[video_id] = 0
        thread = threading.Thread(target=process_video_bg, args=(video_id, filename, filepath))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": "Archivo cargado. Procesamiento iniciado en segundo plano.",
            "video_id": video_id,
            "filename": filename
        })

@app.route('/api/telemetry', methods=['GET'])
def api_telemetry():
    # Fetch last 48 hours of 30-min telemetry
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telemetry ORDER BY timestamp ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/process_demo', methods=['POST'])
def process_demo():
    # If the demo file is not generated, generate it
    demo_filename = "demo_feeding.mp4"
    demo_path = os.path.join(app.config['UPLOAD_FOLDER'], demo_filename)
    
    if not os.path.exists(demo_path):
        import generate_demo_video
        generate_demo_video.create_demo_video(demo_path)
        
    # Copy/Save record in database
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO videos (filename, upload_time, status)
        VALUES (?, ?, ?)
    ''', (demo_filename, datetime.now().isoformat(), 'uploaded'))
    video_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Process
    processing_progress[video_id] = 0
    thread = threading.Thread(target=process_video_bg, args=(video_id, demo_filename, demo_path))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "status": "success",
        "message": "Video de demostración iniciado.",
        "video_id": video_id
    })

def process_video_bg(video_id, filename, filepath):
    try:
        # Update status to processing
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE videos SET status = 'processing' WHERE id = ?", (video_id,))
        conn.commit()
        
        # Load active settings
        settings = database.get_settings()
        roi_settings = {
            'roi_x': int(settings.get('roi_x', 100)),
            'roi_y': int(settings.get('roi_y', 100)),
            'roi_w': int(settings.get('roi_w', 400)),
            'roi_h': int(settings.get('roi_h', 300)),
            'threshold_frenzy': float(settings.get('threshold_frenzy', 60.0)),
            'threshold_satiety': float(settings.get('threshold_satiety', 15.0))
        }
        
        # Output processed video path
        processed_filename = "processed_" + filename
        processed_filepath = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
        
        # Callback function for tracking progress
        def update_progress(pct):
            processing_progress[video_id] = pct
            
        # Run computer vision processing
        stats = cv_processor.process_video(
            input_path=filepath,
            output_path=processed_filepath,
            roi_settings=roi_settings,
            progress_callback=update_progress
        )
        
        # Update database with results and mark completed
        cursor.execute('''
            UPDATE videos 
            SET status = 'completed',
                duration = ?,
                fps = ?,
                frame_count = ?,
                processed_filename = ?,
                turbulence_average = ?,
                fish_count_average = ?,
                fish_lethargic_max = ?,
                fish_erratic_max = ?
            WHERE id = ?
        ''', (
            stats['duration_seconds'],
            stats['fps'],
            stats['frame_count'],
            processed_filename,
            stats['avg_turbulence'],
            stats['avg_fish_count'],
            stats['lethargic_max'],
            stats['erratic_max'],
            video_id
        ))
        
        # Save a new 30-minute interval reading corresponding to this feeding event
        feeding_intensity = stats['max_turbulence']
        feeding_events = 1 if stats['feeding_detected'] else 0
        fish_count = stats['max_fish_count']
        sick_fish_count = stats['lethargic_max'] + stats['erratic_max']
        
        # Environmental simulation variables
        water_temp = 27.2
        dissolved_oxygen = 4.4 if feeding_events == 1 else 5.2
        ph = 7.3
        
        # Comfort status auto-evaluation
        comfort = "Optimal"
        notes = "Evento de alimentación analizado mediante CV"
        
        if sick_fish_count > 0:
            comfort = "Stress"
            notes = f"Alerta CV: Detectados {stats['lethargic_max']} peces letárgicos y {stats['erratic_max']} erráticos (Estrés fisiológico)."
            if sick_fish_count > 3:
                comfort = "Danger"
                notes = f"PELIGRO BIOLÓGICO: Infección/hipoxia severa. {sick_fish_count} peces inactivos/erráticos."
        elif feeding_events == 1 and feeding_intensity < 25.0:
            comfort = "Stress"
            notes = "Advertencia CV: Respuesta de alimentación nula (Estrés fisiológico detectado)"
            
        timestamp_str = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO telemetry 
            (timestamp, fish_count, sick_fish_count, feeding_intensity, feeding_events, water_temperature, dissolved_oxygen, ph_level, comfort_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp_str, fish_count, sick_fish_count, feeding_intensity, feeding_events, water_temp, dissolved_oxygen, ph, comfort, notes))
        
        conn.commit()
        print(f"Video ID {video_id} procesado con éxito. Stats guardadas en la BD.")
        
    except Exception as e:
        print(f"Error procesando el video {video_id}: {str(e)}")
        try:
            cursor.execute("UPDATE videos SET status = 'failed' WHERE id = ?", (video_id,))
            conn.commit()
        except:
            pass
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
