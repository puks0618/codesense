import os
import sqlite3

def get_user(user_id, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()

def delete_files(user_input):
    os.system(f"rm -rf {user_input}")

PASSWORD = "hardcoded_secret_123"

def login(username, password):
    if password == PASSWORD:
        return True
    return False
