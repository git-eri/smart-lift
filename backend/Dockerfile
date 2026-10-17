FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 smartlift \
    && useradd --uid 10001 --gid 10001 --no-create-home smartlift
COPY app ./app
RUN mkdir -p app/data app/binaries && chown smartlift:smartlift app/data
USER smartlift
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
# One worker owns all connections and the movement watchdog. Never add workers
# until the in-memory ownership and STOP state are replaced by shared state.
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--workers=1", "--ws-max-size=4096", "--ws-max-queue=16", "--ws-ping-interval=1", "--ws-ping-timeout=2", "--timeout-graceful-shutdown=5", "--log-config=/code/app/log_conf.yml"]
