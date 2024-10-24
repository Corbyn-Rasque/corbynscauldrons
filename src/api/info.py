from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy import text
from src import database as db

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.
    """
    print(timestamp)

    with db.engine.begin() as connection:
        set_day_from = text("""UPDATE strategy
                               SET is_today = (day_name = :day)""")
    
        connection.execute(set_day_from, {'day': timestamp.day})

    return "OK"