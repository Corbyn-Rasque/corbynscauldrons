from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db
from enum import Enum

class BarrelType(Enum):
    RED     =   [1, 0, 0, 0]
    GREEN   =   [0, 1, 0, 0]
    BLUE    =   [0, 0, 1, 0]
    DARK    =   [0, 0, 0, 1]

    def __str__(self):
        return str(list(self.value))

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """
    Function gets inventory and returns of a tuple containing number of potions, potion volume, and total gold.
    Hardcoded to a single row in the database at this time, and assumes values in the above order.
    """
    with db.engine.begin() as connection:
        red, green, blue, dark, gold = connection.execute(sqlalchemy.text("""SELECT red, green, blue, dark, gold
                                                                             FROM global_inventory""")).first()
        
        num_potions = connection.execute(sqlalchemy.text("""SELECT SUM(qty)
                                                            FROM catalog""")).scalar()

    return {"number_of_potions": num_potions, "ml_in_barrels": (red+green+blue+dark), "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    return {
        "potion_capacity": 0,
        "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """

    with db.engine.begin() as connection:
        num_capacity, vol_capacity = connection.execute(sqlalchemy.text("""SELECT num_capacity, vol_capacity
                                                                           FROM global_inventory""")).first()

        num_capacity = num_capacity + capacity_purchase.potion_capacity
        vol_capacity = vol_capacity + capacity_purchase.ml_capacity

        connection.execute(sqlalchemy.text(f"""UPDATE global_inventory
                                              SET num_capacity = {num_capacity}, vol_capacity = {vol_capacity}"""))

    return "OK"

# For testing inventory
# print(get_inventory())

# deliver_capacity_plan(capacity_purchase = CapacityPurchase(potion_capacity = 1, ml_capacity = 1), order_id = 1)


# ADDS COLUMNS TO STRATEGY

# with db.engine.begin() as connection:
#     week = connection.execute(sqlalchemy.text("""SELECT * FROM strategy""")).all()

#     new_list = []

#     for day in week:
#         temp_list = []

#         for i in range(1, 25, 2):
#             temp_list = list(day)
#             temp_list[-1] = i
#             new_list.append(temp_list)

#     connection.execute(sqlalchemy.text(f"""INSERT INTO strategy (day, red_ratio, green_ratio, blue_ratio, dark_ratio, day_name, hour)
#                                            VALUES {', '.join(map(str, tuple(map(tuple, new_list))))}"""))