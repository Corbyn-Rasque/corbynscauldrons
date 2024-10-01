from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    with db.engine.begin() as connection:
        num_green_potions, num_green_ml, _ = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).first()
        num_green_ml = num_green_ml - (potions_delivered[0].quantity * potions_delivered[0].potion_type[1])
        num_green_potions = num_green_potions + potions_delivered[0].quantity
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions = {num_green_potions}, num_green_ml = {}"))

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.

    with db.engine.begin() as connection:
        num_green_ml = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar()
        num_potions_to_create = num_green_ml // 100

    if num_potions_to_create > 0:
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_ml = {(num_green_ml % 100)}, num_green_potions = {num_potions_to_create}"))
        return [
            {
                "potion_type": [0, 100, 0, 0],
                "quantity": num_potions_to_create
            }
        ]
    else:
        return []

# if __name__ == "__main__":
#     # get_bottle_plan()

#     potions = [PotionInventory(potion_type = [0, 100, 0, 0], quantity = 10)]
#     post_deliver_bottles(potions, 7)