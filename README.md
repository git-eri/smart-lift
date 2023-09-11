# locate-backend
[![pipeline status](https://gitlab.erikj.de/locate/locate-backend/badges/dev/pipeline.svg)](https://gitlab.erikj.de/locate/locate-backend/-/commits/dev)
[![coverage report](https://gitlab.erikj.de/locate/locate-backend/badges/dev/coverage.svg)](https://gitlab.erikj.de/locate/locate-backend/-/commits/dev)
[![Latest Release](https://gitlab.erikj.de/locate/locate-backend/-/badges/release.svg)](https://gitlab.erikj.de/locate/locate-backend/-/releases)


## Getting Started

This project is the backend for the locate project. It is written in python and uses FastAPI as a framework. The database is a mariadb database.

### .env

Take the ```default.env``` file and change the values to your needs. Then rename this file to ```.env```

## Local Development

### What you need

- Docker
- Python 3.10 (pip & venv)

Lint before commit!
```bash
$ pylint app
```

### local python with docker

Run backend containers before running the api locally.

Linux (Ubuntu/Debian)
```bash
$ sudo apt install python3.10-venv libmariadb3 libmariadb-dev
$ python3 -m venv env
$ source ./env/bin/activate
$ pip install -r requirements.txt
$ python3 -m src
```

Windows PowerShell
```powershell
$ python -m venv env
$ .\env\Scripts\Activate.ps1
$ python -m pip install --upgrade pip
$ pip install -r requirements.txt
$ python -m src
```

macOS (Not tested!)
```bash
$ python3 -m venv env
$ source ./env/bin/activate
$ pip install -r requirements.txt
$ python3 -m src
```

## Server
The server handles the communication between the controller and the frontend. It communicates between the clients via websockets and the controller via http requests.

### Development

For local testing

```bash
uvicorn app.main:app --port 8000 --reload --host 0.0.0.0
```

### Deployment

Run the ```deploy.sh``` script.

```bash
$ git clone https://gitlab.erikj.de/git-eri/smart-lift.git
$ cd smart-lift
$ ???
```

## Controller (Pico)

The controller is connected via wifi and should have its own ip address. The server communicates to the controller via http requests. The controller talks back to the server to give information which lifts are active and if the system is healthy.



## What needs to get tested?
- [ ] Checks for invalid calls
- [ ] Checks for leaks
