#!/bin/bash

uvicorn app.main:app --port 8000 --reload --host 0.0.0.0