FROM python:3.13-slim

# Install system dependencies for browser automation
RUN apt-get update && apt-get install -y \
    firefox-esr \
    wget \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install geckodriver for Firefox
RUN wget -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz \
    && tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm /tmp/geckodriver.tar.gz

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers
RUN playwright install firefox

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV DISPLAY=:99

# Expose port for health checks
EXPOSE 8080

# Start command
CMD ["python", "main.py"]
