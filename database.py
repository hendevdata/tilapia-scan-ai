import sqlite3
import os
from datetime import datetime, timedelta
import random

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'aquaculture.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create videos table with health fields
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        upload_time TEXT NOT NULL,
        status TEXT NOT NULL, -- 'uploaded', 'processing', 'completed', 'failed'
        duration REAL,
        fps REAL,
        frame_count INTEGER,
        processed_filename TEXT,
        turbulence_average REAL,
        fish_count_average INTEGER,
        fish_lethargic_max INTEGER DEFAULT 0,
        fish_erratic_max INTEGER DEFAULT 0
    )
    ''')
    
    # Create telemetry table with sick_fish_count
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL UNIQUE,
        fish_count INTEGER NOT NULL,
        sick_fish_count INTEGER DEFAULT 0,
        feeding_intensity REAL NOT NULL, -- 0 to 100
        feeding_events INTEGER NOT NULL,
        water_temperature REAL NOT NULL,
        dissolved_oxygen REAL NOT NULL,
        ph_level REAL NOT NULL,
        comfort_status TEXT NOT NULL,    -- 'Optimal', 'Stress', 'Danger'
        notes TEXT
    )
    ''')
    
    # Create settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    
    # Populate initial default settings if empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        default_settings = [
            ('roi_x', '100'),
            ('roi_y', '100'),
            ('roi_w', '400'),
            ('roi_h', '300'),
            ('threshold_frenzy', '60'),
            ('threshold_satiety', '15'),
            ('temp_min', '25'),
            ('temp_max', '30'),
            ('oxygen_min', '4'),
            ('ph_min', '6.5'),
            ('ph_max', '8.5')
        ]
        cursor.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", default_settings)
        conn.commit()
        
    # Populate historical telemetry if empty
    cursor.execute("SELECT COUNT(*) FROM telemetry")
    if cursor.fetchone()[0] == 0:
        generate_historical_data(conn)
        
    conn.close()

def generate_historical_data(conn):
    cursor = conn.cursor()
    now = datetime.now()
    start_time = now - timedelta(hours=48)
    
    # Align to the nearest 30 minutes
    start_time = start_time.replace(minute=(start_time.minute // 30) * 30, second=0, microsecond=0)
    
    current_time = start_time
    while current_time <= now:
        timestamp_str = current_time.isoformat()
        hour = current_time.hour
        minute = current_time.minute
        
        is_feeding = 1 if hour in [8, 12, 16] and minute == 0 else 0
        
        # Environmental conditions
        temp_base = 26.5 + 2.0 * (1.0 - abs(hour - 15) / 12.0)
        water_temperature = round(temp_base + random.uniform(-0.5, 0.5), 1)
        
        if is_feeding:
            oxygen_base = 4.8
        elif hour >= 22 or hour <= 6:
            oxygen_base = 4.2
        else:
            oxygen_base = 5.8
        dissolved_oxygen = round(oxygen_base + random.uniform(-0.4, 0.4), 1)
        
        ph_base = 7.2 + 0.3 * (1.0 - abs(hour - 14) / 12.0)
        ph_level = round(ph_base + random.uniform(-0.1, 0.1), 1)
        
        # Sick fish simulation based on environmental parameters
        # If oxygen is low or temp is high, more fish get sick/lethargic
        sick_fish_count = 0
        notes = "Nado regular"
        
        if dissolved_oxygen < 4.0:
            sick_fish_count = random.randint(3, 7)
            notes = "Alerta: Peces letárgicos en superficie por bajo oxígeno"
        elif water_temperature > 30.5:
            sick_fish_count = random.randint(2, 5)
            notes = "Advertencia: Peces erráticos por estrés térmico"
        else:
            # 5% chance of 1-2 sick fish under optimal conditions (baseline health)
            if random.random() < 0.15:
                sick_fish_count = random.randint(1, 2)
                notes = "Patrones de nado atípico detectados en 1-2 peces"
        
        if is_feeding:
            feeding_intensity = random.uniform(65.0, 95.0)
            fish_count = random.randint(45, 60)
            if sick_fish_count > 0:
                # If fish are sick, feeding frenzy is slightly reduced
                feeding_intensity -= sick_fish_count * 3
                notes = f"Alimentación programada - Frenesí con {sick_fish_count} peces inactivos"
            else:
                notes = "Alimentación programada - Frenesí fuerte"
        else:
            feeding_intensity = random.uniform(5.0, 20.0)
            fish_count = random.randint(30, 42)
            
        # Determine comfort status
        if water_temperature < 25.0 or water_temperature > 30.0 or dissolved_oxygen < 4.0 or ph_level < 6.5 or ph_level > 8.5:
            comfort_status = "Stress"
            if dissolved_oxygen < 3.2 or water_temperature > 32.0:
                comfort_status = "Danger"
                notes = f"PELIGRO: Oxígeno crítico. {sick_fish_count} peces con letargia severa"
        else:
            comfort_status = "Optimal"
            
        try:
            cursor.execute('''
            INSERT INTO telemetry 
            (timestamp, fish_count, sick_fish_count, feeding_intensity, feeding_events, water_temperature, dissolved_oxygen, ph_level, comfort_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp_str, fish_count, sick_fish_count, feeding_intensity, is_feeding, water_temperature, dissolved_oxygen, ph_level, comfort_status, notes))
        except sqlite3.IntegrityError:
            pass
            
        current_time += timedelta(minutes=30)
        
    conn.commit()

def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    return settings

def update_settings(settings_dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    for key, value in settings_dict.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
