from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """

    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("""UPDATE global_inventory
                                              SET gold = 100, num_capacity = 50, vol_capacity = 10000, red = 0, green = 0, blue = 0, dark = 0"""))
        connection.execute(sqlalchemy.text("""UPDATE catalog
                                              SET qty = 0"""))
        
    return "OK"