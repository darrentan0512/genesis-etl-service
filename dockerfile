FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use gunicorn as the production server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "wsgi:app"]