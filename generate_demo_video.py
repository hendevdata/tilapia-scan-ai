import cv2
import numpy as np
import random
import os

def create_demo_video(filename="demo_feeding.mp4", width=640, height=480, fps=30, duration_sec=15):
    print(f"Generando video de prueba biológico: {filename} ({width}x{height}, {fps} FPS)...")
    
    total_frames = fps * duration_sec
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    # Fish parameters
    num_fish = 35
    fish_list = []
    
    for i in range(num_fish):
        # Program simulated health traits:
        # ID 0 & 1: Lethargic (barely swim, ignore food)
        # ID 2 & 3: Erratic (sudden high velocity standard deviation, sharp turns, spin)
        # Others: Healthy
        health_type = 'healthy'
        if i in [0, 1]:
            health_type = 'lethargic'
        elif i in [2, 3]:
            health_type = 'erratic'
            
        fish_list.append({
            'id': i,
            'health_type': health_type,
            'x': random.uniform(80, width - 80),
            'y': random.uniform(80, height - 80),
            'vx': random.uniform(-1, 1),
            'vy': random.uniform(-1, 1),
            'size': random.randint(13, 19),
            'angle': random.uniform(0, 360)
        })
        
    # Food particles list
    food_particles = []
    
    # Feeding ROI center
    roi_cx, roi_cy = 320, 240
    roi_r = 100
    
    for frame_idx in range(total_frames):
        bg = np.zeros((height, width, 3), dtype=np.uint8)
        bg[:, :] = [35, 20, 10] # BGR (Dark Navy/Slate Blue)
        
        cv2.circle(bg, (width // 2, height // 2), 300, (40, 25, 12), -1)
        cv2.circle(bg, (width // 2, height // 2), 150, (45, 28, 14), -1)
        
        time_sec = frame_idx / fps
        is_feeding_active = 3.0 <= time_sec < 10.0
        is_calming = time_sec >= 10.0
        
        # Update and draw food pellets (brown dots falling)
        if is_feeding_active:
            if frame_idx % 3 == 0:
                food_particles.append({
                    'x': random.uniform(roi_cx - 60, roi_cx + 60),
                    'y': random.uniform(10, 50),
                    'speed': random.uniform(4, 7)
                })
        
        active_food = []
        for fp in food_particles:
            fp['y'] += fp['speed']
            if fp['y'] > roi_cy + random.randint(-40, 40):
                fp['speed'] = random.uniform(0.1, 0.5)
            if fp['y'] < height - 20:
                cv2.circle(bg, (int(fp['x']), int(fp['y'])), 3, (38, 76, 114), -1)
                active_food.append(fp)
        food_particles = active_food

        # Update fish positions
        for fish in fish_list:
            h_type = fish['health_type']
            
            if h_type == 'lethargic':
                # Lethargic fish ignore feeding, float slowly
                fish['vx'] = 0.94 * fish['vx'] + random.uniform(-0.04, 0.04)
                fish['vy'] = 0.94 * fish['vy'] + random.uniform(-0.04, 0.04)
                # Cap speed very low to trigger lethargic warning (<0.5 px/frame)
                fish['vx'] = np.clip(fish['vx'], -0.25, 0.25)
                fish['vy'] = np.clip(fish['vy'], -0.25, 0.25)
                
            elif h_type == 'erratic':
                # Erratic fish swim rapidly in random circles/spirals
                # High speed variance, ignore feeding directions
                fish['vx'] = 0.8 * fish['vx'] + random.uniform(-2.2, 2.2)
                fish['vy'] = 0.8 * fish['vy'] + random.uniform(-2.2, 2.2)
                # Cap hyperactive speed high
                fish['vx'] = np.clip(fish['vx'], -5.5, 5.5)
                fish['vy'] = np.clip(fish['vy'], -5.5, 5.5)
                # Add rotating direction shake
                fish['angle'] += random.uniform(-30, 30)
                
            else: # Healthy fish
                if is_feeding_active and len(food_particles) > 0:
                    target_x = roi_cx + random.uniform(-40, 40)
                    target_y = roi_cy + random.uniform(-40, 40)
                    dx = target_x - fish['x']
                    dy = target_y - fish['y']
                    dist = np.sqrt(dx**2 + dy**2)
                    
                    if dist > 10:
                        fish['vx'] = 0.85 * fish['vx'] + 0.15 * (dx / dist) * 7.5
                        fish['vy'] = 0.85 * fish['vy'] + 0.15 * (dy / dist) * 7.5
                    else:
                        fish['vx'] = random.uniform(-3, 3)
                        fish['vy'] = random.uniform(-3, 3)
                elif is_calming:
                    fish['vx'] = 0.98 * fish['vx'] + random.uniform(-0.1, 0.1)
                    fish['vy'] = 0.98 * fish['vy'] + random.uniform(-0.1, 0.1)
                    fish['vx'] = np.clip(fish['vx'], -2.0, 2.0)
                    fish['vy'] = np.clip(fish['vy'], -2.0, 2.0)
                else:
                    fish['vx'] = 0.95 * fish['vx'] + random.uniform(-0.2, 0.2)
                    fish['vy'] = 0.95 * fish['vy'] + random.uniform(-0.2, 0.2)
                    fish['vx'] = np.clip(fish['vx'], -1.5, 1.5)
                    fish['vy'] = np.clip(fish['vy'], -1.5, 1.5)

            # Move and bounce off edges
            fish['x'] += fish['vx']
            fish['y'] += fish['vy']
            
            if fish['x'] < 30 or fish['x'] > width - 30:
                fish['vx'] *= -1
            if fish['y'] < 30 or fish['y'] > height - 30:
                fish['vy'] *= -1
                
            fish['x'] = np.clip(fish['x'], 15, width - 15)
            fish['y'] = np.clip(fish['y'], 15, height - 15)

            # Calculate heading angle unless overridden
            if h_type != 'erratic':
                fish['angle'] = np.degrees(np.arctan2(fish['vy'], fish['vx']))
            
            # Draw shadow
            shadow_offset = 6
            cv2.ellipse(bg, (int(fish['x']) + shadow_offset, int(fish['y']) + shadow_offset), 
                        (fish['size'], fish['size'] // 2), int(fish['angle']), 0, 360, (20, 10, 5), -1)
            
            # Draw fish body (color slightly varies by health)
            # Healthy = Slate Blue / Gray: (110, 80, 55)
            # Lethargic = Paler, yellowish: (110, 110, 85)
            # Erratic = Stressed darker/reddish details: (90, 60, 60)
            if h_type == 'lethargic':
                body_color = (120, 120, 95)
                tail_color = (95, 95, 75)
            elif h_type == 'erratic':
                body_color = (95, 65, 65)
                tail_color = (75, 50, 50)
            else:
                body_color = (110, 80, 55)
                tail_color = (90, 65, 45)
                
            cv2.ellipse(bg, (int(fish['x']), int(fish['y'])), 
                        (fish['size'], fish['size'] // 2), int(fish['angle']), 0, 360, body_color, -1)
            
            # Tail fin
            rad_angle = np.arctan2(fish['vy'], fish['vx'])
            if h_type == 'erratic':
                rad_angle = np.radians(fish['angle'])
            tail_x = fish['x'] - np.cos(rad_angle) * fish['size']
            tail_y = fish['y'] - np.sin(rad_angle) * fish['size']
            cv2.circle(bg, (int(tail_x), int(tail_y)), fish['size'] // 3, tail_color, -1)

        # Draw feeding turbulence (white splashes)
        if is_feeding_active:
            num_splashes = random.randint(3, 8)
            for _ in range(num_splashes):
                sx = int(roi_cx + random.uniform(-roi_r + 20, roi_r - 20))
                sy = int(roi_cy + random.uniform(-roi_r + 20, roi_r - 20))
                s_radius = random.randint(10, 30)
                color_val = random.randint(180, 255)
                cv2.circle(bg, (sx, sy), s_radius, (color_val, color_val, color_val), random.randint(1, 3))

        # Write frame
        out.write(bg)

    out.release()
    print("Video de prueba biológico generado con éxito.")

if __name__ == "__main__":
    create_demo_video()
