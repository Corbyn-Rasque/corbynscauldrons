from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
from sqlalchemy import text
from src import database as db


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


class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int


# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    '''
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    '''
    
    capacity_plan = CapacityPurchase(potion_capacity = 0, ml_capacity = 0)

    get_gold = text('''SELECT gold
                       FROM global''')

    get_potions_pressure =    text('''WITH reset AS (SELECT timestamp AS time
                                                       FROM resets
                                                       ORDER BY timestamp DESC
                                                       LIMIT 1),
                                             hourly_potion AS (SELECT date_trunc('hour', potion_ledger.timestamp) AS hour,
                                                                   SUM(potion_ledger.qty)::INTEGER AS quantity_sum
                                                               FROM potion_ledger, reset
                                                               WHERE potion_ledger.timestamp >= reset.time
                                                                   AND potion_ledger.timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                                                               GROUP BY hour),
                                             hourly_capacity AS (SELECT date_trunc('hour', capacity_ledger.timestamp) AS hour,
                                                                     SUM(capacity_ledger.potion)::INTEGER AS capacity_sum
                                                                 FROM capacity_ledger, reset
                                                                 WHERE capacity_ledger.timestamp >= reset.time
                                                                 GROUP BY hour)
                            SELECT SUM(quantity_sum) OVER (ORDER BY hourly_potion.hour ASC) AS num_potions,
                                   hourly_capacity2.capacity_sum AS capacity
                            FROM hourly_potion
                            LEFT JOIN LATERAL (SELECT capacity_sum
                                               FROM hourly_capacity
                                               WHERE hourly_capacity.hour <= hourly_potion.hour
                                               ORDER BY hourly_capacity.hour DESC
                                               LIMIT 1) AS hourly_capacity2 ON TRUE
                            ORDER BY hourly_potion.hour ASC''')
    
    get_volume_pressure =   text('''WITH reset AS (SELECT timestamp AS time
                                                   FROM resets
                                                   ORDER BY timestamp DESC
                                                   LIMIT 1),
                                         hourly_barrels AS (SELECT date_trunc('hour', barrel_ledger.timestamp) AS hour,
                                                                   SUM(barrel_ledger.red
                                                                     + barrel_ledger.green
                                                                     + barrel_ledger.blue
                                                                     + barrel_ledger.dark)::INTEGER AS quantity_sum
                                                            FROM barrel_ledger, reset
                                                            WHERE barrel_ledger.timestamp >= reset.time
                                                                AND barrel_ledger.timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                                                            GROUP BY hour),
                                         hourly_capacity AS (SELECT date_trunc('hour', capacity_ledger.timestamp) AS hour,
                                                                    SUM(capacity_ledger.volume)::INTEGER AS volume_sum
                                                             FROM capacity_ledger, reset
                                                             WHERE capacity_ledger.timestamp >= reset.time
                                                             GROUP BY hour)
                                    SELECT SUM(quantity_sum) OVER (ORDER BY hourly_barrels.hour ASC) AS volume, hourly_capacity2.volume_sum AS capacity
                                    FROM hourly_barrels
                                    LEFT JOIN LATERAL (SELECT volume_sum
                                                       FROM hourly_capacity
                                                       WHERE hourly_capacity.hour <= hourly_barrels.hour
                                                       ORDER BY hourly_capacity.hour DESC
                                                       LIMIT 1) AS hourly_capacity2 ON TRUE
                                    ORDER BY hourly_barrels.hour ASC''')
    
    with db.engine.begin() as connection:
        
        gold = connection.execute(get_gold).one()
        potion_pressure = connection.execute(get_potions_pressure).all()
        volume_pressure = connection.execute(get_volume_pressure).all()
    
    if potion_pressure and min([(inventory - potions) for (potions, inventory) in potion_pressure]) < 5:
        capacity_plan.potion_capacity = 1 if gold > 2000 else 0
        gold -= 1000

    if volume_pressure and min([(inventory - volume) for (volume, inventory) in volume_pressure]) < 500:
        capacity_plan.potion_capacity = 1 if gold > 2000 else 0

    return dict(capacity_plan)


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