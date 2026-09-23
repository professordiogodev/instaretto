FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system appuser && useradd --system --create-home --gid appuser appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY wsgi.py .

# Created here (not just at runtime) so a fresh named volume mounted at
# this path inherits appuser ownership instead of root's.
RUN mkdir -p /var/log/instaretto && chown appuser:appuser /var/log/instaretto

USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "wsgi:app"]
