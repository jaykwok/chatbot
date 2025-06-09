FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and templates
COPY *.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Create user first
RUN useradd -m appuser

# Create directories and set proper ownership
RUN mkdir -p /app/logs /app/knowledge_base && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# Switch to non-root user
USER appuser

# Configure environment
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# Run with Gunicorn
CMD ["gunicorn", "--timeout", "180", "--bind", "0.0.0.0:1011", "--access-logfile", "-", "--error-logfile", "-", "app:app"]