FROM python:3.10-slim

# System dependencies for PDF/DOCX parsing
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt .

# Create venv
RUN python -m venv /app/venv

# Activate venv + install deps
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy rest of code
COPY . .

# Use venv by default
ENV PATH="/app/venv/bin:$PATH"

# Expose FastAPI port
EXPOSE 8000

CMD ["bash"]