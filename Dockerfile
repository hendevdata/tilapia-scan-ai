# Use official Python runtime
FROM python:3.10-slim

# Install system dependencies for OpenCV and FFmpeg inside Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir imageio imageio-ffmpeg

# Copy application files
COPY . .

# Create uploads and processed folders
RUN mkdir -p uploads processed

# Expose the Flask port
EXPOSE 5000

# Set environment variable for Flask production/dev
ENV FLASK_ENV=production

# Run server
CMD ["python", "app.py"]
