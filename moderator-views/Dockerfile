FROM python:3.12-slim

WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# Install the specified packages
RUN pip install -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Set environment variable for Flask
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=1

# Expose port
EXPOSE 5002

# Run Flask app
CMD ["python", "app.py"]