from fastapi import APIRouter
import sqlalchemy
from sqlalchemy import text
from src import database as db
from src.api import bottler

router = APIRouter()

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    '''
    Each unique item combination must have only a single price.
    '''

    get_catalog =   text('''WITH reset AS (SELECT timestamp AS time
                                           FROM resets
                                           ORDER BY timestamp DESC
                                           LIMIT 1)
                            SELECT catalog.name AS sku,
                                   catalog.name AS name,
                                   COALESCE(SUM(potion_ledger.qty), 0)::INT AS quantity,
                                   catalog.price AS price,
                                   ARRAY[catalog.r, catalog.g, catalog.b, catalog.d] AS potion_type
                            FROM catalog
                            JOIN reset ON TRUE
                            JOIN potion_ledger ON (potion_ledger.red, potion_ledger.green, potion_ledger.blue, potion_ledger.dark)
                                 IN ((catalog.r, catalog.g, catalog.b, catalog.d))
                            WHERE potion_ledger.timestamp >= reset.time AND catalog.listed
                            GROUP BY catalog.name, catalog.price, catalog.r, catalog.g, catalog.b, catalog.d''')

    with db.engine.begin() as connection:
        potions = connection.execute(get_catalog).mappings().all()

    return potions

if __name__ == '__main__':
     print(get_catalog())