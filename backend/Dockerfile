FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

#RUN curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--log-config=app/log_conf.yml", "--ssl-keyfile=app/certs/server.key", "--ssl-certfile=app/certs/server.crt"]

# If running behind a proxy like Nginx or Traefik add --proxy-headers
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers"]