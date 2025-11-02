FROM python:3.13-alpine
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
COPY ./app /code/app
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000", "--log-config=app/log_conf.yml"]
