FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies
RUN dnf install -y git && dnf clean all

# Install Node.js for JS build step
RUN curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - && \
    dnf install -y nodejs && dnf clean all

# Install Python dependencies
COPY lambdas/rebuild_worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/worker-requirements.txt

# Copy Lambda handler to task root
COPY lambdas/rebuild_worker/handler.py ${LAMBDA_TASK_ROOT}/

# Copy full project source to /opt/site
# (.dockerignore excludes .git, node_modules, infrastructure, lambdas, frontends, etc.)
COPY . /opt/site/

# Ensure all files are readable (some scripts may have restrictive permissions)
RUN chmod -R a+rX /opt/site

# Install Node.js dependencies for esbuild in the project copy
RUN cd /opt/site && npm install --omit=dev 2>/dev/null || true

CMD ["handler.lambda_handler"]
