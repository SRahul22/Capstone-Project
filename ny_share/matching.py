import time 
import h3
from collections import defaultdict
import mysql.connector
from matching_config import DB_CONFIG


MAX_SEARCH_RADIUS = 5
SLEEP_BETWEEN_BATCHES = 2  # IN SECONDS


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def find_driver_expanding_search(cursor, origin_h3):
    """
    Searches for an available driver in expanding k-rings.
    Returns driver_id or None.
    """
    checked_cells = set()

    for k in range(0, MAX_SEARCH_RADIUS + 1):
        current_disk = h3.k_ring(origin_h3, k)
        new_cells = [cell for cell in current_disk if cell not in checked_cells]

        if not new_cells:
            continue

        checked_cells.update(new_cells)

        format_strings = ','.join(['%s'] * len(new_cells))
        query = f"""
            SELECT driver_id, h3_hash
            FROM drivers_live
            WHERE h3_hash IN ({format_strings})
              AND number_of_passengers = 0
            LIMIT 1
        """

        cursor.execute(query, tuple(new_cells))
        driver = cursor.fetchone()

        if driver:
            print(f"  → Driver found in ring {k} ≈ {k * 0.6:.1f}–{k * 1.2:.1f} km")
            return driver[0]

    return None


def process_matches():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  

        # 1. Get waiting customers, oldest first
        cursor.execute("""
            SELECT customer_id, origin_h3, destination_h3,
                   request_time
            FROM customers_live
            ORDER BY request_time ASC
        """)
        customers = cursor.fetchall()


        if not customers:
            print("No waiting customers.")
            return



        grouped = defaultdict(list)
        for c in customers:
            key = (c['origin_h3'], c['destination_h3'])
            grouped[key].append(c)

        print(f"Processing {len(customers)} customers in {len(grouped)} route groups")




        for (origin_h3, dest_h3), queue in grouped.items():
            print(f"\nRoute {origin_h3} → {dest_h3} : {len(queue)} waiting")

            i = 0 
            drivers_used_in_this_batch = set()

            while len(queue)>=2:
                rider1 = queue[0]
                rider2 = queue[1]

                driver_id = find_driver_expanding_search(cursor, origin_h3)

                if not driver_id:
                    print(f'No driver near location')
                    break
                
                cursor.execute("""
                    UPDATE drivers_live
                    SET number_of_passengers = 2
                    WHERE driver_id = %s
                      AND number_of_passengers = 0
                """, (driver_id,))

                try:
                    insert_sql = """
                        INSERT INTO active_rides
                        (driver_id, customer_id, origin_latitude, origin_longitude,
                         destination_latitude, destination_longitude,
                         origin_h3, destination_h3, start_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """

                    # Insert Ride 1
                    cursor.execute(insert_sql, (
                        driver_id, rider1['customer_id'],
                        rider1['origin_latitude'], rider1['origin_longitude'],
                        rider1['destination_latitude'], rider1['destination_longitude'],
                        origin_h3, dest_h3
                    ))

                    # Insert Ride 2
                    cursor.execute(insert_sql, (
                        driver_id, rider2['customer_id'],
                        rider2['origin_latitude'], rider2['origin_longitude'],
                        rider2['destination_latitude'], rider2['destination_longitude'],
                        origin_h3, dest_h3
                    ))

                    # Remove customers from waitlist
                    cursor.execute("DELETE FROM customers_live WHERE customer_id IN (%s, %s)", 
                                   (rider1['customer_id'], rider2['customer_id']))

                    conn.commit()
                    print(f"   ✅ MATCH SUCCESS! Driver {driver_id} assigned.")

                    del queue[0]
                    del queue[1]

                except Exception as e:
                    print(f"   -> Database Error during commit: {e}")
                    conn.rollback()
        

    except Exception as e:
        print(f"Critical error in matcher: {e}")
        if conn:
            conn.rollback()

    finally:
        if cursor: cursor.close()
        if conn: conn.close()


if __name__ == "__main__":
    print(f"🚕 Dynamic Ride Matcher Started | Radius: {MAX_SEARCH_RADIUS} rings")
    print("───────────────────────────────────────────────────────────────")

    while True:
        try:
            process_matches()
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print(f"Main loop error: {e}")
        
        time.sleep(SLEEP_BETWEEN_BATCHES)



