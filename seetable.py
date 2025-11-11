import sqlite3
import os

DB_NAME = "fitmate.db"

def view_table_data(cursor, table_name):
    """Fetches and prints all data from a specified table."""
    print(f"\n--- Data in table: {table_name} ---")
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            print("  (Table is empty)")
            return

        # Get column names
        column_names = [description[0] for description in cursor.description]
        print("  Columns:", ", ".join(column_names))
        print("-" * (len(table_name) + 20)) # Separator

        # Print rows
        for row in rows:
            print(f"  {row}")

    except sqlite3.Error as e:
        print(f"  Error reading from table {table_name}: {e}")


def view_database_contents():
    """Connects to the database and displays contents of specific tables."""
    if not os.path.exists(DB_NAME):
        print(f"Error: Database file '{DB_NAME}' not found.")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        print(f"Connected to database: {DB_NAME}")

        # View data from exercise_type table
        view_table_data(cursor, "exercise_type")

        # View data from training_types table
        view_table_data(cursor, "training_types")

        print("\n--- Data viewing complete ---")

    except sqlite3.Error as e:
        print(f"\n--- DATABASE ERROR: {e} ---")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Run the viewing script ---
if __name__ == "__main__":
    view_database_contents()
