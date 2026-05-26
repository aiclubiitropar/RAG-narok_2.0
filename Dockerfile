FROM python:3.11-slim

# Install system dependencies (Redis and Supervisor)
RUN apt-get update && apt-get install -y \
    redis-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user that HF Spaces expects (uid 1000)
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Copy the backend requirements and install them
COPY --chown=user:user backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend source code
COPY --chown=user:user backend/ ./backend/

# Copy the supervisor configuration
COPY --chown=user:user supervisord.conf ./

# Set environment variables for HF Space
ENV PORT=7860
ENV HOST=0.0.0.0
# Tell the app to use the local Redis server running in the container
ENV REDIS_URL=redis://localhost:6379/0
ENV CELERY_BROKER_URL=redis://localhost:6379/0

# Make sure the log directory for supervisor exists and is writable
RUN mkdir -p /home/user/app/logs && chown user:user /home/user/app/logs

# Switch to the non-root user
USER user

# Expose the HF Space port
EXPOSE 7860

# Run supervisor to start Redis, Celery, and FastAPI
CMD ["supervisord", "-c", "/home/user/app/supervisord.conf"]
