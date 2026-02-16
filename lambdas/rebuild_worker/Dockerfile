FROM public.ecr.aws/lambda/python:3.12 AS base

# Install system dependencies
RUN dnf install -y git && dnf clean all

# Install Node.js for JS build step
RUN curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - && \
    dnf install -y nodejs && dnf clean all

# Copy requirements and install Python dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy the project source
# Note: In production, the rebuild worker needs the full project.
# The Docker build context should be the repo root (set via CDK asset path).
COPY . ${LAMBDA_TASK_ROOT}/

# Install Node.js dependencies for esbuild
RUN cd ${LAMBDA_TASK_ROOT} && npm install --omit=dev 2>/dev/null || true

CMD ["handler.lambda_handler"]
