FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY evals ./evals
COPY scripts ./scripts
COPY synthetic_data ./synthetic_data
RUN pip install --no-cache-dir ".[aws,telemetry]" \
    && useradd --create-home --uid 10001 copilot \
    && mkdir -p /app/data /app/evals/reports \
    && chown -R copilot:copilot /app
USER copilot
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
