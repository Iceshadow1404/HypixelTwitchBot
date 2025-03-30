# Use Python 3.12 as the base image
FROM python:3.12-slim

# Set working directory in the container
WORKDIR /app

# Copy requirements.txt to the working directory
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Command to run when the container starts
CMD ["python" ,"main.py"]