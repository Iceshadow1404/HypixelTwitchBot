FROM python:3.12-slim

# Install Node.js (v18 LTS) and other dependencies
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (incl. start.sh and networth.js)
COPY . .

# Install Node.js dependencies
RUN npm install express skyhelper-networth

# Make the start script executable
RUN chmod +x start.sh

# Disable Python output buffering
ENV PYTHONUNBUFFERED=1

# Run both scripts
CMD ["./start.sh"]
