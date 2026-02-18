import h3
import time
import threading
import mysql.connector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

# Import settings
from drivers_live_config import DB_CONFIG, H3_RESOLUTION, DRIVER_TIMEOUT_MINUTES, CLEANUP_INTERVAL_SECONDS

app = FastAPI()

# --- Pydantic Model ---
class DriverUpdate(BaseModel):
    driver_id: int
    current_lat: float
    current_lon: float
    vehicle_type: str = "sedan"
    number_of_passengers: int = 0

# --- Database Helper ---
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- Background Task: The "Janitor" ---
# This runs separately and removes drivers who haven't pinged in 20 mins
def cleanup_inactive_drivers():
    print(f"Driver cleanup service started. Removing drivers inactive for > {DRIVER_TIMEOUT_MINUTES} mins.")
    
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # SQL logic: Delete rows where 'last_updated' is older than X minutes ago
            query = f"""
            DELETE FROM drivers_live 
            WHERE last_updated < (NOW() - INTERVAL {DRIVER_TIMEOUT_MINUTES} MINUTE)
            """
            
            cursor.execute(query)
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"[{datetime.now()}] Removed {cursor.rowcount} inactive drivers.")
            
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Cleanup Error: {e}")
        
        # Wait 60 seconds before checking again
        time.sleep(CLEANUP_INTERVAL_SECONDS)

# Start the background thread when the API starts
cleaner_thread = threading.Thread(target=cleanup_inactive_drivers, daemon=True)
cleaner_thread.start()


@app.get("/")
def read_root():
    return {"message": "Driver API is running successfully!"}

# --- API Endpoint: Update Driver Location ---
@app.post("/update_driver_location/")
async def update_driver_location(update: DriverUpdate):
    conn = None
    try:
        # 1. Calculate H3
        h3_hash = h3.latlng_to_cell(update.current_lat, update.current_lon, H3_RESOLUTION)

        # 2. Update DB (Upsert)
        conn = get_db_connection()
        cursor = conn.cursor()

        # This query updates the 'last_updated' timestamp automatically
        query = """
        INSERT INTO drivers_live 
        (driver_id, current_latitude, current_longitude, vehicle_type, number_of_passengers, h3_hash)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            current_latitude = VALUES(current_latitude),
            current_longitude = VALUES(current_longitude),
            vehicle_type = VALUES(vehicle_type),
            number_of_passengers = VALUES(number_of_passengers),
            h3_hash = VALUES(h3_hash),
            last_updated = CURRENT_TIMESTAMP
        """

        values = (
            update.driver_id,
            update.current_lat,
            update.current_lon,
            update.vehicle_type,
            update.number_of_passengers,
            h3_hash
        )

        cursor.execute(query, values)
        conn.commit()

        return {"status": "success", "driver_id": update.driver_id, "h3": h3_hash}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()