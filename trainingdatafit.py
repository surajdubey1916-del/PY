import sqlite3
import json # To potentially store instructions better later if schema changes
import os

DB_NAME = "fitmate.db"

# --- Data Definition ---
# CHANGED: Structure is now: { 'exercise_key': [Instructions List] }
# The duration (e.g., ", 1)") has been removed from every line.

EXERCISE_DATA = {
    # Strength
    "pushups": ["Start in plank position", "Lower body until chest nearly touches floor", "Push back up to starting position", "Keep core tight and back straight"],
    "squats": ["Stand with feet shoulder-width apart", "Lower hips back and down", "Keep chest up and knees behind toes", "Return to standing position"],
    "plank": ["Start on hands and knees", "Lower onto forearms", "Keep body in straight line", "Engage core and hold position"],
    "glute_bridges": ["Lie on back with knees bent", "Lift hips toward ceiling", "Squeeze glutes at the top", "Lower back down slowly"],
    # Endurance
    "high_knees": ["Run in place at high speed", "Bring knees up to chest level", "Pump arms vigorously", "Maintain fast pace"],
    "jumping_jacks": ["Stand with feet together", "Jump while spreading legs", "Raise arms overhead", "Return to starting position"],
    "butt_kicks": ["Jog in place quickly", "Kick heels up to glutes", "Maintain rhythm and pace", "Keep core engaged"],
    "mountain_climbers": ["Start in plank position", "Bring right knee to chest", "Quickly switch legs", "Maintain steady rhythm"],
    # Balance
    "calf_raises": ["Stand with feet hip-width", "Rise up onto toes", "Hold at the top", "Lower slowly back down"],
    "side_leg_raises": ["Stand holding onto support", "Lift one leg out to side", "Keep body straight", "Lower slowly with control"],
    "tree_pose": ["Stand on one leg", "Place foot on inner thigh", "Bring hands to prayer position", "Hold and breathe deeply"],
    "side_stepping": ["Step side to side slowly", "Maintain upright posture", "Use support if needed", "Controlled movements"],
    # Flexibility
    "forward_bend": ["Stand with feet together", "Slowly bend forward from hips", "Reach for toes or shins", "Hold for 20-30 seconds"],
    "quad_stretch": ["Stand holding onto support", "Bend one knee and grab ankle", "Gently pull heel toward glutes", "Keep knees close together"],
    "hamstring_stretch": ["Sit with one leg extended", "Bend other leg with foot to thigh", "Reach toward extended foot", "Hold for 20-30 seconds"],
    "cat_cow": ["Start on hands and knees", "Arch back upward (cat)", "Drop belly downward (cow)", "Flow between positions"],
    # From Full Body (if not already defined)
    "lunges": ["Stand with feet together", "Step forward with one leg", "Lower hips until both knees bent 90°", "Push back to start position"],
    # Added Arm Circles based on previous data seen
    "arm_circles": ["Stand with feet shoulder-width apart, extend arms to the sides.", "Make small circles, then large circles, forward and backward."]
}

# Structure: (Training Name, List of Exercise Keys)
# This data does not need to change.
TRAINING_DATA = [
    ("Strength Training", ["pushups", "squats", "plank", "glute_bridges"]),
    ("Endurance Training", ["high_knees", "jumping_jacks", "butt_kicks", "mountain_climbers"]),
    ("Balance Training", ["calf_raises", "side_leg_raises", "tree_pose", "side_stepping"]),
    ("Flexibility Training", ["forward_bend", "quad_stretch", "hamstring_stretch", "cat_cow"]),
    ("Full Body Training", ["squats", "plank", "lunges", "glute_bridges"]),
    ("Warmup", ["arm_circles", "butt_kicks", "high_knees", "lunges"])
]

# --- Database Population Function ---

def populate_database():
    """
    Clears and inserts data into exercise_type and training_types tables
    based on the *new* schema (no duration).
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        print(f"Connected to database: {DB_NAME}")

        # --- 1. Clear Existing Data ---
        print("Clearing existing data from exercise_type and training_types tables...")
        cur.execute("DELETE FROM exercise_type")
        cur.execute("DELETE FROM training_types")
        cur.execute("DELETE FROM sqlite_sequence WHERE name='exercise_type'")
        cur.execute("DELETE FROM sqlite_sequence WHERE name='training_types'")
        print("Existing data cleared.")

        # --- 2. Insert Exercises ---
        print("\nInserting exercises into exercise_type...")
        exercise_key_to_id = {}
        
        # --- THIS BLOCK IS CHANGED ---
        for ex_key, instructions_list in EXERCISE_DATA.items():
            # Join list into a single string with newlines for TEXT column
            instructions_text = "\n".join(instructions_list)
            # We no longer get a duration

            cur.execute('''INSERT INTO exercise_type
                               (name, instructions)
                               VALUES (?, ?)''',
                            (ex_key, instructions_text))
            
            exercise_id = cur.lastrowid
            exercise_key_to_id[ex_key] = exercise_id
            print(f"  Inserted exercise: '{ex_key}' (ID: {exercise_id})")
        # --- END OF CHANGED BLOCK ---

        # --- 3. Insert Training Plans ---
        # This part does not need to change, as it only uses names and IDs.
        print("\nInserting training plans into training_types...")
        for t_name, ex_keys in TRAINING_DATA:
            ids_for_training = []
            valid_keys = True
            for key in ex_keys:
                if key in exercise_key_to_id:
                    ids_for_training.append(str(exercise_key_to_id[key]))
                else:
                    print(f"  [Warning] Exercise key '{key}' not found for training '{t_name}'. Skipping.")
                    valid_keys = False
                    break

            if valid_keys:
                exercise_ids_str = ",".join(ids_for_training)
                cur.execute('''INSERT INTO training_types
                               (name, exercise_ids)
                               VALUES (?, ?)''',
                            (t_name, exercise_ids_str))
                training_id = cur.lastrowid
                print(f"  Inserted training plan: '{t_name}' (ID: {training_id}), Exercises linked: [{exercise_ids_str}]")

        conn.commit()
        print("\n✅ Success: Database populated.")

    except sqlite3.Error as e:
        print(f"\n❌ DATABASE ERROR: {e}")
        if conn:
            conn.rollback() # Roll back changes on error
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

# --- Run the population script ---
if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        print(f"Error: Database file '{DB_NAME}' not found.")
        print("Please run your main Kivy app (main.py) once to create the database file before running this script.")
    else:
        populate_database()