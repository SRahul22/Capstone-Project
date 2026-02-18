import h3
import time
import threading
import mysql.connector
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Import Configuration ---
from customers_live_config import DB_CONFIG, CLEANUP_INTERVAL_SECONDS, DEFAULT_WAIT_TIME_MINUTES

app = FastAPI()

# --- Pydantic Model (Input Validation) ---
class CustomerRequest(BaseModel):
    customer_id: int
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    # Optional: User can override the default wait time
    minutes_to_wait: int = DEFAULT_WAIT_TIME_MINUTES 

# --- Database Helper ---
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- Background Task: The Auto-Deleter ---
# This runs separately from the API to keep things fast
def cleanup_expired_records():
    print(f"Background cleaner started. Checking every {CLEANUP_INTERVAL_SECONDS} seconds...")
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Logic: Delete any row where 'time_to_leave' is less than the current time
            query = "DELETE FROM customers_live WHERE time_to_leave < NOW()"
            cursor.execute(query)
            conn.commit()
            
            if cursor.rowcount > 0:
                print(f"[{datetime.now()}] Cleaned up {cursor.rowcount} expired records.")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Cleanup Error: {e}")
        
        # Wait before checking again
        time.sleep(CLEANUP_INTERVAL_SECONDS)

# Start the background thread when the app launches
cleaner_thread = threading.Thread(target=cleanup_expired_records, daemon=True)
cleaner_thread.start()

# --- API Endpoint ---
@app.post("/request_ride/")
async def create_customer_request(request: CustomerRequest):
    conn = None
    try:
        # 1. Calculate H3 Indices (Resolution 9 is standard for urban areas)
        origin_h3 = h3.latlng_to_cell(request.origin_lat, request.origin_lon, 9)
        dest_h3 = h3.latlng_to_cell(request.dest_lat, request.dest_lon, 9)

        # 2. Calculate Expiration Time
        request_time = datetime.now()
        time_to_leave = request_time + timedelta(minutes=request.minutes_to_wait)

        # 3. Insert into MySQL
        conn = get_db_connection()
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO customers_live 
        (customer_id, origin_latitude, origin_longitude, destination_latitude, destination_longitude, 
         origin_h3, destination_h3, request_time, time_to_leave)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            request.customer_id,
            request.origin_lat, request.origin_lon,
            request.dest_lat, request.dest_lon,
            origin_h3, dest_h3,
            request_time, time_to_leave
        )

        cursor.execute(insert_query, values)
        conn.commit()
        
        return {
            "status": "success", 
            "customer_id": request.customer_id,
            "origin_h3": origin_h3,
            "time_to_leave": time_to_leave
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()