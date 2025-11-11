# reset_database.py
import os

# The name of the database file you want to delete.
# This must match the DB_NAME in your main.py.
DB_FILE = "fitmate.db"

def main():
    """
    Checks if the database file exists and deletes it.
    """
    print("--- Database Reset Script ---")
    
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print(f"✅ Success: '{DB_FILE}' has been deleted.")
        except OSError as e:
            print(f"❌ Error: Failed to delete file. Reason: {e}")
    else:
        print(f"ℹ️ Info: '{DB_FILE}' not found. Nothing to delete.")

if __name__ == "__main__":
    main()