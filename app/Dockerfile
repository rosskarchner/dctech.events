FROM python:3.13-slim AS builder

WORKDIR /app

# Install AWS CLI and other dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x freeze.py lambda_function.sh

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_DEBUG=1

# Expose port
EXPOSE 5000

# Default command
CMD ["python", "app.py"]