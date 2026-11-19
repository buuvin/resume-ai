FROM python:3.10-slim

# System dependencies for PDF/DOCX parsing
RUN apt-get update && apt-get install -y \
    --no-install-recommends git\
    build-essential \
    poppler-utils \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt .

# Ensure pip is up-to-date
RUN pip install --upgrade pip

# Install dependencies globally in the container
RUN pip install --no-cache-dir -r requirements.txt

# Download the spaCy model required by keyphrase-vectorizers.
# Not available as a regular PyPI dependency.
RUN python -m spacy download en_core_web_sm

# Copy rest of code
COPY . . 

# Expose FastAPI port
EXPOSE 8000
