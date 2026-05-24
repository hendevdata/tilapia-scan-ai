# Use official lightweight Python image
FROM python:3.10-slim

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

# Set environment variable for Flask production
ENV FLASK_ENV=production

# Run server
CMD ["python", "app.py"]
