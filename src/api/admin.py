from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from sqlalchemy import text
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    '''
    Resets the game state by creating a new timestamp, afterwhich all things will
    be considered. Default potion & barrel capacity added along with - 100 cost
    to initialize to + 100 gold overall.
    '''

    reset = text('''INSERT INTO resets
                    DEFAULT VALUES;
                 
                    INSERT INTO capacity_ledger
                    DEFAULT VALUES;''')

    with db.engine.begin() as connection:
        connection.execute(reset);
        
    return "OK"