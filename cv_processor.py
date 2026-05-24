import cv2
import numpy as np
import os
import time
import imageio

class CentroidTracker:
    def __init__(self, max_disappeared=15, max_distance=50):
        self.next_object_id = 0
        self.objects = {}
        self.disappeared = {}
        self.history = {} # Track path history: obj_id -> list of centroids
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid):
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.history[self.next_object_id] = [centroid]
        self.next_object_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]
        if object_id in self.history:
            del self.history[object_id]

    def update(self, rects):
        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
            return self.objects

        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for (i, (startX, startY, endX, endY)) in enumerate(rects):
            cX = int((startX + endX) / 2.0)
            cY = int((startY + endY) / 2.0)
            input_centroids[i] = (cX, cY)

        if len(self.objects) == 0:
            for i in range(len(input_centroids)):
                self.register(input_centroids[i])
        else:
            object_ids = list(self.objects.keys())
            object_centroids = list(self.objects.values())

            D = np.linalg.norm(np.array(object_centroids)[:, np.newaxis] - input_centroids, axis=2)

            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            used_rows = set()
            used_cols = set()

            for (row, col) in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                if D[row, col] > self.max_distance:
                    continue

                object_id = object_ids[row]
                self.objects[object_id] = input_centroids[col]
                self.disappeared[object_id] = 0
                
                # Append to track path history (limit to 35 frames)
                if object_id not in self.history:
                    self.history[object_id] = []
                self.history[object_id].append(input_centroids[col])
                if len(self.history[object_id]) > 35:
                    self.history[object_id].pop(0)

                used_rows.add(row)
                used_cols.add(col)

            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)

            for row in unused_rows:
                object_id = object_ids[row]
                self.disappeared[object_id] += 1
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)

            for col in unused_cols:
                self.register(input_centroids[col])

        return self.objects


def process_video(input_path, output_path, roi_settings, progress_callback=None):
    """
    Processes video using OpenCV and encodes with ImageIO (H.264 web compatible).
    - Unified single-pass Background Subtraction (MOG2) on blurred full frame.
    - Scales area filters dynamically based on resolution.
    - Filters out massive contours (reflections, camera shake).
    - Tracks fish centroids and maintains movement trajectory histories.
    - Classifies individual fish as 'SANO', 'LETARGICO' (slow speed), or 'ERRATICO' (high velocity variance).
    - Measures motion turbulence inside the ROI.
    - Detects food pellets using a hybrid HSV color + small motion contour algorithm.
    - Overlay HUD with live charts written as web-compatible MP4.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video {input_path}")

    # Video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Scale factor calculations relative to base 640x480 resolution
    resolution_area = width * height
    scale_factor = resolution_area / 307200.0
    
    # Dynamic tracking parameter adjustment
    max_track_distance = int(55 * np.sqrt(scale_factor))
    
    # Setup H.264 video writer using imageio
    try:
        writer = imageio.get_writer(output_path, fps=fps, codec='h264', quality=8)
        use_imageio = True
        print(f"Iniciando codificador H.264 (ImageIO) para el video: {output_path}")
    except Exception as e:
        print(f"Error cargando ImageIO H.264 writer: {e}. Usando cv2.VideoWriter (MPEG4 fallback).")
        use_imageio = False
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Initialize CV algorithms (MOG2 background subtractor)
    fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=False)
    tracker = CentroidTracker(max_disappeared=20, max_distance=max_track_distance)
    
    # ROI parameters (Fallback to defaults if invalid)
    rx = roi_settings.get('roi_x', int(width * 0.15))
    ry = roi_settings.get('roi_y', int(height * 0.15))
    rw = roi_settings.get('roi_w', int(width * 0.7))
    rh = roi_settings.get('roi_h', int(height * 0.6))
    
    # Thresholds
    threshold_frenzy = roi_settings.get('threshold_frenzy', 60.0)
    threshold_satiety = roi_settings.get('threshold_satiety', 15.0)

    # Variables for stats
    frame_idx = 0
    turbulence_history = []
    fish_counts = []
    
    # Sick fish tracking counters
    max_lethargic_in_frame = 0
    max_erratic_in_frame = 0
    
    food_detected_frames = 0
    frenzy_duration_frames = 0
    
    # HSV thresholds for brown pellets (food)
    lower_brown = np.array([4, 20, 30])
    upper_brown = np.array([32, 200, 220])

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1. Image preprocessing (Gaussian Blur to reduce ripples noise)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        
        # Apply background subtraction to the full frame (Unified single-pass)
        fgmask = fgbg.apply(blurred)
        
        # Clean mask using morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fgmask_cleaned = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
        fgmask_cleaned = cv2.morphologyEx(fgmask_cleaned, cv2.MORPH_CLOSE, kernel)
        
        # Crop cleaned mask to ROI for turbulence/motion analysis
        roi_mask = fgmask_cleaned[ry:ry+rh, rx:rx+rw]
        
        # Calculate Turbulence Index: ratio of motion pixels in the ROI
        motion_pixels = np.sum(roi_mask == 255)
        roi_area = rw * rh
        raw_turbulence = (motion_pixels / roi_area) * 100.0 if roi_area > 0 else 0
        
        # Soft temporal smoothing (moving average of last 5 frames)
        if len(turbulence_history) > 0:
            smoothed_turbulence = 0.75 * raw_turbulence + 0.25 * turbulence_history[-1]
        else:
            smoothed_turbulence = raw_turbulence
        
        smoothed_turbulence = min(100.0, smoothed_turbulence)
        turbulence_history.append(smoothed_turbulence)

        # 2. Fish detection based on motion contours
        contours, _ = cv2.findContours(fgmask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rects = []
        for c in contours:
            area = cv2.contourArea(c)
            # Scale area constraints based on video resolution
            min_area = 130 * scale_factor
            max_area = 12000 * scale_factor
            
            if min_area < area < max_area:
                (x, y, w, h) = cv2.boundingRect(c)
                # Filter out huge noise (camera shifts, glare)
                if w > width * 0.45 or h > height * 0.45:
                    continue
                rects.append((x, y, x + w, y + h))

        # Update centroid tracker
        tracked_objects = tracker.update(rects)
        current_fish_count = len(tracked_objects)
        fish_counts.append(current_fish_count)

        # 3. Hybrid Food Pellet Detection
        # Slices HSV values of ROI
        roi_img = frame[ry:ry+rh, rx:rx+rw]
        hsv_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
        food_mask = cv2.inRange(hsv_roi, lower_brown, upper_brown)
        food_mask_cleaned = cv2.morphologyEx(food_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        
        color_contours, _ = cv2.findContours(food_mask_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        color_pellets = 0
        for cc in color_contours:
            c_area = cv2.contourArea(cc)
            if (2 * scale_factor) < c_area < (150 * scale_factor):
                color_pellets += 1
                
        # Count small moving blobs in the ROI mask too
        roi_motion_contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_pellets = 0
        for rmc in roi_motion_contours:
            rmc_area = cv2.contourArea(rmc)
            if (2 * scale_factor) < rmc_area < (120 * scale_factor):
                motion_pellets += 1

        # Hybrid detection: brown color blobs are present OR multiple small moving objects drop
        food_present = color_pellets > 2 or (motion_pellets > 6 and smoothed_turbulence > 4.0)
        if food_present:
            food_detected_frames += 1

        # Classify behavior state
        if smoothed_turbulence > threshold_frenzy:
            behavior_state = "FRENESI ALIMENTICIO"
            state_color = (0, 0, 255)
            frenzy_duration_frames += 1
        elif smoothed_turbulence > threshold_satiety:
            behavior_state = "NADO ACTIVO"
            state_color = (0, 255, 255)
        else:
            behavior_state = "NADO PASIVO / SACIADO"
            state_color = (0, 255, 0)

        # 4. Fish health diagnosis & rendering
        overlay = frame.copy()
        
        # Keep track of diagnosed categories in this specific frame
        frame_lethargic = 0
        frame_erratic = 0
        
        # Draw ROI Rectangle
        cv2.rectangle(overlay, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 2)
        cv2.putText(overlay, "ROI ALIMENTACION", (rx + 5, ry - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45 * np.sqrt(scale_factor), (255, 255, 0), 1, cv2.LINE_AA)

        # Diagnose each fish based on its trajectory history
        for (obj_id, centroid) in tracked_objects.items():
            cx, cy = centroid
            
            # Diagnostic defaults
            diagnosis = "SANO"
            color_diag = (0, 255, 200) # Neon Cyan for healthy BGR
            
            # Analyze kinematic history of coordinates (need at least 15 frames)
            pts = tracker.history.get(obj_id, [])
            if len(pts) >= 15:
                # Calculate consecutive step displacements
                steps = [np.linalg.norm(np.array(pts[i]) - np.array(pts[i-1])) for i in range(1, len(pts))]
                avg_speed = np.mean(steps)
                speed_std = np.std(steps)
                
                # Sickness threshold parameters scaled by resolution
                lethargic_speed_limit = 0.55 * np.sqrt(scale_factor)
                erratic_variance_limit = 5.2 * np.sqrt(scale_factor)
                
                if avg_speed < lethargic_speed_limit:
                    diagnosis = "LETARGICO"
                    color_diag = (0, 165, 255) # Orange/Amber BGR
                    frame_lethargic += 1
                elif speed_std > erratic_variance_limit:
                    diagnosis = "ERRATICO"
                    color_diag = (0, 0, 255) # Red BGR (Panicked/disease swimming)
                    frame_erratic += 1
            
            # Draw tracking center dot
            cv2.circle(overlay, (cx, cy), int(4 * np.sqrt(scale_factor)), color_diag, -1)
            
            # Print diagnostic tag next to ID
            lbl = f"ID {obj_id} [{diagnosis}]"
            cv2.putText(overlay, lbl, (cx + int(5*np.sqrt(scale_factor)), cy - int(5*np.sqrt(scale_factor))), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38 * np.sqrt(scale_factor), color_diag, 1, cv2.LINE_AA)
            
            # Draw bounding box matching diagnosis
            for (startX, startY, endX, endY) in rects:
                if startX <= cx <= endX and startY <= cy <= endY:
                    cv2.rectangle(overlay, (startX, startY), (endX, endY), color_diag, 1)
                    break
        
        # Accumulate peak sickness metrics
        max_lethargic_in_frame = max(max_lethargic_in_frame, frame_lethargic)
        max_erratic_in_frame = max(max_erratic_in_frame, frame_erratic)

        # Alpha blend overlay details
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

        # Draw Header HUD (Black translucent bar)
        hud_h = int(80 * np.sqrt(scale_factor)) if height > 480 else 80
        hud_overlay = frame.copy()
        cv2.rectangle(hud_overlay, (0, 0), (width, hud_h), (20, 20, 20), -1)
        cv2.addWeighted(hud_overlay, 0.75, frame, 0.25, 0, frame)
        
        # HUD Text items
        txt_size = 0.5 * np.sqrt(scale_factor)
        cv2.putText(frame, "ACUICULTURA 4.0 | DIAGNOSTICO DE SALUD", (15, int(hud_h * 0.35)), 
                    cv2.FONT_HERSHEY_SIMPLEX, txt_size * 1.1, (255, 255, 255), 2, cv2.LINE_AA)
        
        cv2.putText(frame, f"SITUACION: LETARGIA: {frame_lethargic} | ERRATICOS: {frame_erratic}", (15, int(hud_h * 0.75)), 
                    cv2.FONT_HERSHEY_SIMPLEX, txt_size, (200, 200, 200), 1, cv2.LINE_AA)
        
        cv2.putText(frame, f"PECES TOTALES: {current_fish_count}", (width - int(450 * np.sqrt(scale_factor)), int(hud_h * 0.35)), 
                    cv2.FONT_HERSHEY_SIMPLEX, txt_size, (255, 255, 255), 1, cv2.LINE_AA)
        
        cv2.putText(frame, f"TURBULENCIA ROI: {smoothed_turbulence:.1f}%", (width - int(450 * np.sqrt(scale_factor)), int(hud_h * 0.75)), 
                    cv2.FONT_HERSHEY_SIMPLEX, txt_size, (255, 255, 255), 1, cv2.LINE_AA)
        
        food_status = "ALIMENTO DETECTADO" if food_present else "SIN ALIMENTO"
        food_color = (0, 165, 255) if food_present else (128, 128, 128)
        cv2.putText(frame, f"PELLETS: {food_status}", (width - int(200 * np.sqrt(scale_factor)), int(hud_h * 0.55)), 
                    cv2.FONT_HERSHEY_SIMPLEX, txt_size, food_color, 2, cv2.LINE_AA)

        # Draw a mini real-time graph of Turbulence
        graph_w = int(160 * np.sqrt(scale_factor))
        graph_h = int(60 * np.sqrt(scale_factor))
        graph_x, graph_y = width - graph_w - 20, height - graph_h - 20
        
        graph_bg = frame.copy()
        cv2.rectangle(graph_bg, (graph_x, graph_y), (graph_x + graph_w, graph_y + graph_h), (15, 15, 15), -1)
        cv2.addWeighted(graph_bg, 0.6, frame, 0.4, 0, frame)
        cv2.rectangle(frame, (graph_x, graph_y), (graph_x + graph_w, graph_y + graph_h), (80, 80, 80), 1)
        cv2.putText(frame, "HIST. TURBULENCIA", (graph_x + 5, graph_y - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35 * np.sqrt(scale_factor), (200, 200, 200), 1, cv2.LINE_AA)
        
        pts_count = len(turbulence_history)
        max_pts = graph_w
        start_idx = max(0, pts_count - max_pts)
        pts = turbulence_history[start_idx:]
        
        if len(pts) > 1:
            for idx in range(1, len(pts)):
                x1 = graph_x + idx - 1
                y1 = int(graph_y + graph_h - (pts[idx - 1] / 100.0) * (graph_h - 4) - 2)
                x2 = graph_x + idx
                y2 = int(graph_y + graph_h - (pts[idx] / 100.0) * (graph_h - 4) - 2)
                y1 = max(graph_y + 2, min(graph_y + graph_h - 2, y1))
                y2 = max(graph_y + 2, min(graph_y + graph_h - 2, y2))
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 200), 1)

        # Write frame (convert BGR to RGB if writing with imageio)
        if use_imageio:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            writer.append_data(frame_rgb)
        else:
            out.write(frame)
        
        # Progress callback
        frame_idx += 1
        if progress_callback and frame_idx % 10 == 0:
            pct = int((frame_idx / total_frames) * 100.0)
            progress_callback(pct)

    # Release resources
    cap.release()
    if use_imageio:
        writer.close()
    else:
        out.release()

    # Calculate final stats
    avg_turbulence = float(np.mean(turbulence_history)) if turbulence_history else 0.0
    max_turbulence = float(np.max(turbulence_history)) if turbulence_history else 0.0
    avg_fish_count = int(np.mean(fish_counts)) if fish_counts else 0
    max_fish_count = int(np.max(fish_counts)) if fish_counts else 0
    feeding_detected = food_detected_frames > (fps * 1.5)

    return {
        'duration_seconds': total_frames / fps,
        'fps': fps,
        'frame_count': total_frames,
        'avg_turbulence': avg_turbulence,
        'max_turbulence': max_turbulence,
        'avg_fish_count': avg_fish_count,
        'max_fish_count': max_fish_count,
        'lethargic_max': max_lethargic_in_frame,
        'erratic_max': max_erratic_in_frame,
        'feeding_detected': feeding_detected,
        'frenzy_duration_seconds': frenzy_duration_frames / fps
    }
