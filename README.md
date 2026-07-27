# Tilapia Scan AI 🐟 - Acuicultura 4.0

**Tilapia Scan AI** es un sistema de monitoreo biológico inteligente para estanques de piscicultura y cultivo de tilapia. Utiliza **Visión por Computadora (CV)** en el borde (*Edge Computing*) para rastrear el comportamiento de los peces, estimar el frenesí alimentario y diagnosticar tempranamente patrones de estrés fisiológico o patologías (peces letárgicos o erráticos).

---

## 🌟 Características Principales

- 📹 **Procesamiento de Video en Tiempo Real**: Análisis de grabaciones o streaming del estanque usando detección de movimiento por sustracción de fondo (`MOG2`) y seguimiento cinemático de centroides.
- ⚡ **Índice de Turbulencia y Frenesí**: Medición del nivel de agresividad en la alimentación para optimizar el suministro de alimento y evitar desperdicios o sobrealimentación.
- 🩺 **Diagnóstico de Salud Biológica**:
  - **Peces Sanos**: Movimiento regular con velocidad promedio óptima.
  - **Peces Letárgicos**: Nado pausado o flotación lenta por hipoxia / falta de oxígeno.
  - **Peces Erráticos**: Variaciones bruscas de velocidad o pánico indicativos de estrés térmico o infección.
- 🎯 **Calibración de Región de Interés (ROI)**: Delimitación configurable de la zona donde cae el alimento para ignorar el oleaje periférico.
- 📊 **Panel de Telemetría e Históricos**: Monitoreo de temperatura, oxígeno disuelto, pH y estado de confort biológico con alertas automáticas.

---

## ⚙️ Requisitos e Instalación

### Prerrequisitos
- Python 3.9 o superior
- FFmpeg (opcional, para codificación avanzada de video)

### Pasos de Instalación

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/hendevdata/tilapia-scan-ai.git
   cd tilapia-scan-ai
   ```

2. **Crear y activar el entorno virtual**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecutar la aplicación**:
   ```bash
   python app.py
   ```
   *Por defecto, la aplicación se iniciará en `http://127.0.0.1:5050`.*

---

## 🚀 Uso de la Aplicación Web

Una vez que el servidor esté activo:
1. Abre tu navegador e ingresa a `http://127.0.0.1:5050`.
2. **Monitoreo Local**: Observa los indicadores KPI de confort biológico, la calidad estimada del agua y los eventos de turbulencia.
3. **Procesar Videos**: Sube videos en formato `.mp4` para analizarlos o presiona **"Simular Alimentación"** para probar la visión artificial con el video demostrativo.
4. **Calibración ROI**: Configura los límites de píxeles y umbrales de movimiento en la pestaña de calibración.

---

## 🛠️ Estructura del Proyecto

```
tilapia-scan-ai/
├── app.py                     # Servidor Web Flask y API REST
├── cv_processor.py            # Motor de Visión por Computadora y Tracking
├── database.py                # Gestión de base de datos SQLite (Modo WAL)
├── generate_demo_video.py     # Generador de video sintético para demostraciones
├── requirements.txt           # Dependencias del proyecto
├── static/                    # Archivos estáticos (CSS, JS)
│   ├── css/style.css
│   └── js/
│       ├── dashboard.js
│       └── uploader.js
└── templates/
    └── index.html             # Interfaz de usuario (HTML5)
```

---

## 📡 API REST Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/telemetry` | Obtiene el historial de registros biológicos y ambientales. |
| `GET` | `/api/videos` | Lista todos los videos procesados y en cola. |
| `POST` | `/upload` | Sube y procesa un nuevo video del estanque. |
| `POST` | `/api/process_demo` | Genera y procesa un video de prueba sintético. |
| `GET/POST` | `/api/settings` | Obtiene o actualiza la configuración de ROI y umbrales. |

---

## 📄 Licencia

Desarrollado para el proyecto **Acuicultura 4.0 - Piloto V1.0**. Todos los derechos reservados.
