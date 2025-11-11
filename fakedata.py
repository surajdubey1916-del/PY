# populate_fake_history.py
import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_NAME = "fitmate.db"

def populate_fake_history():
    """
    Populates the DB with FAKE USER HISTORY (workouts and weights)
    if it's empty.
    """
    if not os.path.exists(DB_NAME):
        print(f"❌ Error: Database file '{DB_NAME}' not found.")
        print("Please run main.py once to create the database.")
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        # Check if fake user data (workouts) already exists
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = 1")
        workout_count = cur.fetchone()[0]
    
        if workout_count > 0:
            print(f"✅ Fake user history (workouts/weights) already exists. Skipping.")
            conn.close()
            return
        
        print("🅿️ Populating database with fake user history (workouts and weights)...")

        # 1. Add Fake User History
        user_id = 1
        today = datetime.now()

        # Add sample weight data
        print("   ... adding fake weight data")
        for i in range(7):
            day = today - timedelta(days=i)
            weight = round(random.uniform(70.0, 72.0) - (i * 0.1), 2)
            cur.execute("INSERT INTO weights (user_id, weight, date) VALUES (?, ?, ?)", (user_id, weight, day.strftime("%Y-%m-%d")))

        # Add sample workout history
        print("   ... adding fake workout data")
        # Get some valid plan names from the DB to use for the fake history
        cur.execute("SELECT name FROM training_types LIMIT 3")
        plan_names = [row[0] for row in cur.fetchall()]
        
        # If the DB has no plans yet, use a fallback list
        if not plan_names:
            plan_names = ['Full Body Training', 'Warmup', 'Endurance Training']
        
        for i in range(10):
            day = today - timedelta(days=random.randint(0, 14))
            duration = random.randint(15, 60)
            calories = duration * random.randint(5, 10) # 5-10 cal/min
            workout_type = random.choice(plan_names)
            cur.execute("INSERT INTO workouts (user_id, type, duration, calories, date) VALUES (?, ?, ?, ?, ?)", (user_id, workout_type, duration, calories, day.strftime("%Y-%m-%d")))

        conn.commit()
        print("✅ Success: Database has been populated with fake user history!")

    except sqlite3.Error as e:
        print(f"❌ Error: An error occurred during user history population: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    populate_fake_history()