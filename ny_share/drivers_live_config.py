# config.py

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', 
    'password': 'root',  # <--- UPDATE THIS
    'database': 'nammayatri'
}

H3_RESOLUTION = 9 
DRIVER_TIMEOUT_MINUTES = 20  # <--- New setting: Drivers expire after 20 mins
CLEANUP_INTERVAL_SECONDS = 60 # Check for inactive drivers every minute