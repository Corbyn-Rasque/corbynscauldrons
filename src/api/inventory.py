from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
from sqlalchemy import text
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
    '''
    Returns inventory from a view table that calculates potions over potion_ledger, barrel volumes
    over barrel_ledger, and gold over potion_ledger, barrel_ledger & capacity_ledger.
    '''
    with db.engine.begin() as connection:
        inventory = connection.execute(text('''Select num_potions, ml_in_barrels, gold
                                               FROM global''')).mappings().one()

    return dict(inventory)


# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    '''
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    '''

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
    '''
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    '''

    deliver_capacity =  text('''WITH new_ledger AS (INSERT INTO capacity_ledger (potion, volume, cost)
                                                    SELECT :potion_capacity, :ml_capacity,
                                                            ((:potion_capacity / 50) + (:ml_capacity / 10000)) * 1000
                                                    RETURNING id)
                                INSERT INTO capacity_ledger_deliveries (capacity_id, order_id)
                                SELECT new_ledger.id, :order_id
                                FROM new_ledger''')

    with db.engine.begin() as connection:
        connection.execute(deliver_capacity, dict(capacity_purchase) | {"order_id": order_id})

    return "OK"