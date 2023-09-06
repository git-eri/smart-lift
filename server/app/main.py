"""FastAPI main module."""
from typing import Union

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    """Should return the main page of the API."""
    return {"Hello": "World"}


@app.get("/liftup/{lift_id}")
def lift_up(lift_id: int, query: Union[str, None] = None):
    """Move corrosponding lift down"""
    return {"lift_id": lift_id, "q": query, "status": "OK"}

@app.get("/liftdown/{lift_id}")
def lift_down(lift_id: int, query: Union[str, None] = None):
    """Move corrosponding lift down"""
    return {"lift_id": lift_id, "q": query, "status": "OK"}

@app.get("/liftlock/{lift_id}")
def lift_lock(lift_id: int, query: Union[str, None] = None):
    """Lock corrosponding lift"""
    return {"lift_id": lift_id, "q": query, "status": "OK"}
