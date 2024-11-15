from fastapi import APIRouter
import sqlalchemy
from sqlalchemy import text
from src import database as db
from src.api import bottler

router = APIRouter()

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    date = {'day': int}
    best_matches = []
    with db.engine.begin() as connection:

        date['day'], deviation = connection.execute(text("""SELECT day, deviation
                                                            FROM strategy
                                                            WHERE is_today = TRUE""")).first()

        target_potions = connection.execute(text("""SELECT r, g, b, d
                                                    FROM strategy_potions
                                                    WHERE day = :day"""), date).all()

        for potion in target_potions:
            best_matches.append(connection.execute(text(f"""WITH target_potion AS (SELECT *
                                                                                   FROM (VALUES {potion})
                                                                                   AS t(red, green, blue, dark)),
                                                                            distance AS (
                                                                                     SELECT r, g, b, d, qty, price,
                                                                                            SQRT(POWER(catalog.r - target_potion.red, 2) +
                                                                                                 POWER(catalog.g - target_potion.green, 2) +
                                                                                                 POWER(catalog.b - target_potion.blue, 2) +
                                                                                                 POWER(catalog.d - target_potion.dark, 2)
                                                                                        ) AS distance
                                                                                     FROM catalog, target_potion )
                                                                        SELECT r, g, b, d, qty, price
                                                                        FROM distance
                                                                        WHERE distance <= {deviation} AND qty > 0
                                                                        ORDER BY distance ASC
                                                                        LIMIT {6 // len(target_potions)}""")).all())
        
        upcoming = bottler.get_bottle_plan()
        for potion in upcoming:
            potion['potion_type'] = tuple(potion['potion_type'])

        # print([(*potion['potion_type'], potion['quantity']) for potion in upcoming])

        # print( [(*potion['potion_type'],) for potion in upcoming])

        test = connection.execute(text("""SELECT price
                                          FROM catalog
                                          WHERE (r, g, d, b) IN (:potion_type)
                                          """), upcoming).all()
        
        print(test)

        toggle_listed = []
        for targets in filter(None, best_matches):
            for potion in targets:
                    toggle_listed.append(potion[:4])

        if toggle_listed:
            connection.execute(text(f"""UPDATE catalog
                                                SET listed = CASE
                                                        WHEN (r, g, b, d) IN (VALUES {', '.join(str(potion) for potion in toggle_listed)}) THEN TRUE
                                                        ELSE FALSE
                                                END;"""))

    for_sale = []
    for match_list in best_matches:
        for potion in match_list:
            for_sale.append({'sku': ''.join([str(num).zfill(3) for num in potion[:4]]),
                             'name': ''.join([str(num).zfill(3) for num in potion[:4]]),
                             'quantity': potion[4],
                             'price': potion[5],
                             'potion_type': potion[:4],
                            })

    return for_sale

if __name__ == '__main__':
     print(get_catalog())