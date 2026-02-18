# config.py

# Database credentials
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # <--- Update this
    'database': 'nammayatri',
    'auth_plugin': 'mysql_native_password' # Optional: useful if you have login issues
}

# API Settings
CLEANUP_INTERVAL_SECONDS = 60  # How often (in seconds) we check for expired records
DEFAULT_WAIT_TIME_MINUTES = 15 # Default time-to-live if the user doesn't specify one