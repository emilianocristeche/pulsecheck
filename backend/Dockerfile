FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user. /app/data holds the SQLite database (see
# docker-compose.yml) and must be writable by that user.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/data \
    && chown app:app /app/data
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
