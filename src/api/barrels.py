from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """
    This function will record your barrel purchase to your database.
    """
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    for barrel in barrels_delivered:
        if barrel.sku == 'SMALL_GREEN_BARREL':
            with db.engine.begin() as connection:
                current = connection.execute(sqlalchemy.text("SELECT num_green_potions, num_green_ml FROM global_inventory")).all()
                total_ml = current[0][1] + ( barrel.quantity * barrel.ml_per_barrel )
                total_qty = current[0][0] + barrel.quantity
                connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions = {total_qty}, num_green_ml = {total_ml}"))
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """
    This function will send your purchase order to the barrel seller.
    """
    print(wholesale_catalog)

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))

        potions, _, gold = result.first()

        if potions < 10 and gold > 0:
            return [
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 1
                }
            ]
        else:
            return [
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 0
                }
            ]

my_catalog = [Barrel(sku='MEDIUM_RED_BARREL', ml_per_barrel=2500, potion_type=[1, 0, 0, 0], price=250, quantity=10),
Barrel(sku='SMALL_RED_BARREL', ml_per_barrel=500, potion_type=[1, 0, 0, 0], price=100, quantity=10),
Barrel(sku='MEDIUM_GREEN_BARREL', ml_per_barrel=2500, potion_type=[0, 1, 0, 0], price=250, quantity=10),
Barrel(sku='SMALL_GREEN_BARREL', ml_per_barrel=500, potion_type=[0, 1, 0, 0], price=100, quantity=1),
Barrel(sku='MEDIUM_BLUE_BARREL', ml_per_barrel=2500, potion_type=[0, 0, 1, 0], price=300, quantity=10),
Barrel(sku='SMALL_BLUE_BARREL', ml_per_barrel=500, potion_type=[0, 0, 1, 0], price=120, quantity=10),
Barrel(sku='MINI_RED_BARREL', ml_per_barrel=200, potion_type=[1, 0, 0, 0], price=60, quantity=1),
Barrel(sku='MINI_GREEN_BARREL', ml_per_barrel=200, potion_type=[0, 1, 0, 0], price=60, quantity=1),
Barrel(sku='MINI_BLUE_BARREL', ml_per_barrel=200, potion_type=[0, 0, 1, 0], price=60, quantity=1)]

# get_wholesale_purchase_plan(wholesale_catalog = my_catalog)

post_deliver_barrels(my_catalog, order_id=7)