FROM python:3.13-alpine
ENV USE_SSL=false
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
COPY ./app /code/app
COPY ./start.sh ./start.sh
RUN chmod +x ./start.sh
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
CMD ["./start.sh"]
