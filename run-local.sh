#!/bin/bash

#uvicorn app.main:app --port 8000 --reload --host 0.0.0.0
uvicorn app.main:app --host=0.0.0.0 --port=8000 --log-config=app/log_conf.yml