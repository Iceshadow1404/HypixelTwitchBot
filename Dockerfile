FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Python-Buffering deaktivieren
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "main.py"]