# Comprehensive_fitness_app.py
import sqlite3
from datetime import datetime, date, timedelta
import calendar
import random
from functools import partial
import logging
import json
import os
logging.getLogger('matplotlib').setLevel(logging.WARNING)

import matplotlib.pyplot as plt
from kivy.lang import Builder
from kivy.properties import StringProperty, ColorProperty, ObjectProperty, NumericProperty
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.uix.behaviors import ButtonBehavior
from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.anchorlayout import MDAnchorLayout
from kivymd.uix.behaviors import RectangularRippleBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton, MDTextButton, MDRaisedButton
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.card import MDCard
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog import MDDialog
from kivy.uix.scrollview import ScrollView
from kivy_garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.chip import MDChip
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.list import OneLineAvatarIconListItem, IconRightWidget,IconLeftWidget

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Google Generative AI not installed. Using mock mode.")
from kivy.graphics import Color, Ellipse, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.video import Video
from kivy.clock import Clock

COLORS = {
    "background": (0.1, 0.1, 0.15, 1),
    "surface": (0.15, 0.15, 0.2, 1),
    "primary": (0.0, 0.8, 0.8, 1),
    "primary_dark": (0.0, 0.6, 0.6, 1),
    "secondary": (0.3, 0.8, 0.8, 1),
    "text_primary": (1, 1, 1, 1),
    "text_secondary": (0.8, 0.8, 0.8, 1),
    "text_muted": (0.6, 0.6, 0.7, 1),
    "success": (0.2, 0.8, 0.4, 1),
    "warning": (0.9, 0.7, 0.1, 1),
    "error": (0.9, 0.3, 0.3, 1),
    "instructions_bg": (0.2, 0.2, 0.25, 1),
    "instructions_text": (1, 1, 1, 1)
}

KV=open("fitness.kv", "r").read()


class BackgroundBoxLayout(MDBoxLayout):
    """An MDBoxLayout with a background color."""
    def __init__(self, bg_color, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15),])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class CircularTimer(BoxLayout):
    """A circular timer widget."""
    progress = NumericProperty(0)
    time_text = StringProperty("00:00")
    title = StringProperty("Timer")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint = (None, None)
        self.size = (dp(100), dp(100))
        self.spacing = dp(-15)
        
        with self.canvas.before:
            Color(*COLORS["surface"])
            self.bg_circle = Ellipse(pos=self.pos, size=self.size)
            Color(*COLORS["primary"])
            self.progress_arc = Ellipse(pos=self.pos, size=self.size)
        
        self.time_label = MDLabel(
            text=self.time_text,
            font_style='H6',
            bold=True,
            halign='center',
            theme_text_color="Custom",
            text_color=COLORS["text_primary"]
        )
        self.add_widget(self.time_label)
        
        self.title_label = MDLabel(
            text=self.title,
            font_style='Caption',
            halign='center',
            theme_text_color="Custom",
            text_color=COLORS["text_secondary"]
        )
        self.add_widget(self.title_label)
        self.bind(pos=self.update_graphics, size=self.update_graphics, progress=self.update_graphics)

    def update_graphics(self, *args):
        self.bg_circle.pos = self.pos
        self.bg_circle.size = self.size
        
        progress_diameter = self.size[0] * self.progress
        self.progress_arc.pos = (
            self.pos[0] + (self.size[0] - progress_diameter) / 2,
            self.pos[1] + (self.size[1] - progress_diameter) / 2
        )
        self.progress_arc.size = (progress_diameter, progress_diameter)

    def update_progress(self, progress, time_text, title=None):
        self.progress = progress
        self.time_label.text = time_text
        if title:
            self.title_label.text = title

class Training:
    """
    Represents a single training plan, loaded from the database.
    """
    def __init__(self, training_type_id, db_name="fitmate.db"):
        self.training_type_id = training_type_id
        self.name = ""
        self.exercises = []  
        self.durations = [] 
        
        # To prevent infinite loops (Plan A calls B, B calls A)
        self._plans_being_loaded = {training_type_id} 

        conn = None
        try:
            conn = sqlite3.connect(db_name)
            cur = conn.cursor()
            
            # Fetch the top-level training plan
            cur.execute("SELECT name, exercise_ids FROM training_types WHERE unique_id = ?", (self.training_type_id,))
            plan_data = cur.fetchone()

            if plan_data:
                self.name = plan_data[0]
                exercise_ids_str = plan_data[1]
                if exercise_ids_str:
                    self._load_exercises(exercise_ids_str.split(','), cur)
            else:
                print(f"❌ Training plan with ID {self.training_type_id} not found in database")
                
        except sqlite3.Error as e:
            print(f"❌ Database error while loading Training {self.training_type_id}: {e}")
        finally:
            if conn:
                conn.close()

    def _load_exercises(self, exercise_id_list, cur):
        """
        Private helper function to recursively load exercises and plans.
        """
        for item_id_str in exercise_id_list:
            item_id_str = item_id_str.strip()
            
            # CASE 1: It's a nested plan (e.g., "P5")
            if item_id_str.startswith('P'):
                try:
                    plan_id = int(item_id_str[1:])
                    
                    if plan_id in self._plans_being_loaded:
                        print(f" WARNING: Circular dependency detected! Skipping nested plan {plan_id}.")
                        continue
                    
                    self._plans_being_loaded.add(plan_id)
                    
                    cur.execute("SELECT exercise_ids FROM training_types WHERE unique_id = ?", (plan_id,))
                    sub_plan_data = cur.fetchone()
                    
                    if sub_plan_data:
                        sub_exercise_ids_str = sub_plan_data[0]
                        # RECURSION: Call this function again with the new list
                        self._load_exercises(sub_exercise_ids_str.split(','), cur)
                    
                    self._plans_being_loaded.remove(plan_id) 
                    
                except Exception as e:
                    print(f"Error loading nested plan {item_id_str}: {e}")

            # CASE 2: It's a break (e.g., "-1")
            elif item_id_str == "-1":
                self.exercises.append({
                    'id': -1,
                    'name': 'Break Time',
                    'instructions': 'Rest for 1 minute.',
                    'duration': 1 
                })
                self.durations.append(1)
            
            # CASE 3: It's a normal exercise (e.g., "5")
            else:
                try:
                    ex_id = int(item_id_str)
                    cur.execute("SELECT unique_id, name, instructions FROM exercise_type WHERE unique_id = ?", (ex_id,))
                    ex_data = cur.fetchone()
                    if ex_data:
                        self.exercises.append({
                            'id': ex_data[0],
                            'name': ex_data[1],
                            'instructions': ex_data[2] or "No instructions available",
                            'duration': 1  
                        })
                        self.durations.append(1) 
                except Exception as e:
                    print(f"Error loading exercise {item_id_str}: {e}")

class WorkoutScreen(MDScreen):
    training_plan = ObjectProperty(None)
    exercises = []
    current_index = 0
    total_workout_seconds = 0
    elapsed_workout_seconds = 0
    
    exercise_timer = 0
    initial_exercise_time = 0
    
    timer_event = None
    workout_timer_event = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'workout'
        self.app = MDApp.get_running_app()
        self.build_ui()

    def build_ui(self):
        # Main layout for the workout screen
        self.main_layout = MDBoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(20)
        )
        self.main_layout.md_bg_color = COLORS["background"]
        
        # 1. Exercise Name
        self.exercise_label = MDLabel(
            text="Loading...",
            font_style='H4', bold=True, halign='center',
            theme_text_color="Primary",
            adaptive_height=True
        )
        self.main_layout.add_widget(self.exercise_label)
        
        # 2. Exercise Progress
        self.progress_label = MDLabel(
            text="", font_style='Body1', halign='center',
            theme_text_color="Secondary", adaptive_height=True
        )
        self.main_layout.add_widget(self.progress_label)
        
        # 3. Video Player Container
        self.video_container = MDBoxLayout(
            size_hint_y=0.4,
            size_hint_x=1,
            md_bg_color=COLORS["surface"],
            radius=[dp(15),],
            padding=dp(10)
        )
        self.video_player = Video(state='stop', allow_stretch=True)
        self.video_player.bind(eos=self._loop_video)
        self.video_not_found_label = MDLabel(
            text="✗ Video file not found",
            font_style='Body1', halign='center', theme_text_color="Error"
        )
        self.video_container.add_widget(self.video_player)
        self.main_layout.add_widget(self.video_container)

        # 4. Instructions
        self.instructions_container = BackgroundBoxLayout(
            bg_color=COLORS["instructions_bg"],
            orientation='vertical', padding=dp(15), spacing=dp(5),
            size_hint_y=0.3,
            adaptive_height=False,
            radius=[dp(15),]
        )
        instruction_scroll = ScrollView(size_hint_y=1, do_scroll_x=False)
        self.instructions_box = MDBoxLayout(
            orientation='vertical',
            adaptive_height=True,
            padding=(dp(10), dp(5))
        )
        instruction_scroll.add_widget(self.instructions_box)
        self.instructions_container.add_widget(instruction_scroll)
        self.main_layout.add_widget(self.instructions_container)

        # 5. Timers Layout (Horizontal)
        timers_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(20),
            size_hint_y=None,
            height=dp(100),
            pos_hint={'center_x': 0.5},
            adaptive_width=True
        )
        self.exercise_timer_widget = CircularTimer()
        self.workout_timer_widget = CircularTimer()
        timers_layout.add_widget(Widget(size_hint_x=None, width=dp(20)))
        timers_layout.add_widget(self.exercise_timer_widget)
        timers_layout.add_widget(self.workout_timer_widget)
        timers_layout.add_widget(Widget(size_hint_x=None, width=dp(20)))
        self.main_layout.add_widget(timers_layout)

        # 6. Stop Button
        self.stop_btn = MDRaisedButton(
            text='STOP WORKOUT',
            on_release=self.end_workout_dialog,
            pos_hint={'center_x': 0.5},
            md_bg_color=COLORS["error"],
            size_hint_y=None,
            height=dp(50)
        )
        self.main_layout.add_widget(self.stop_btn)

        self.add_widget(self.main_layout)

        # 7. Completion Layout
        self.completion_layout = MDBoxLayout(
            orientation='vertical', padding=dp(50), spacing=dp(30),
            adaptive_height=False,
            size_hint=(1, 1),
            pos_hint={'center_y': 0.5},
        )
        self.completion_layout.md_bg_color = COLORS["background"]
        congrats_label = MDLabel(
            text='WORKOUT COMPLETE', font_style='H5', bold=True,
            halign='center', theme_text_color="Custom", text_color=COLORS["success"]
        )
        self.stats_label = MDLabel(
            text="", 
            font_style='Body1', 
            theme_text_color="Primary",
            halign='center',
            size_hint_y=None,
            adaptive_height=True,
            text_size=(self.width - dp(100), None)
        )
        back_btn = MDRaisedButton(
            text='BACK TO MENU',
            on_release=self.go_to_home,
            pos_hint={'center_x': 0.5}
        )
        completion_center = MDAnchorLayout(anchor_x='center', anchor_y='center')
        completion_box = MDBoxLayout(orientation='vertical', adaptive_size=True, spacing=dp(30))
        completion_box.add_widget(congrats_label)
        completion_box.add_widget(self.stats_label)
        completion_box.add_widget(back_btn)
        completion_center.add_widget(completion_box)
        self.completion_layout.add_widget(completion_center)

    def _loop_video(self, instance, value):
        if value:
            instance.seek(0)
            instance.state = 'play'

    def start_new_workout(self, training_plan):
        # Ensure completion layout is not showing
        if self.completion_layout.parent == self:
            self.remove_widget(self.completion_layout)
            self.add_widget(self.main_layout)

        self.training_plan = training_plan
        self.exercises = self.training_plan.exercises
        self.current_index = 0
        self.elapsed_workout_seconds = 0
        
        if not self.exercises:
            self.show_error("No exercises found in this training plan!")
            return
        self.total_workout_seconds = sum(self.training_plan.durations) * 60
        if self.workout_timer_event:
            self.workout_timer_event.cancel()
        self.workout_timer_event = Clock.schedule_interval(self.update_workout_time, 1)

        self.update_workout_time_display()
        self.start_next_exercise()

    def show_error(self, message):
        toast(message)
        self.go_to_home()

    def update_workout_time_display(self):
        total_minutes = self.total_workout_seconds // 60
        total_seconds_rem = self.total_workout_seconds % 60

        elapsed_minutes = self.elapsed_workout_seconds // 60
        elapsed_seconds_rem = self.elapsed_workout_seconds % 60

        workout_progress = self.elapsed_workout_seconds / self.total_workout_seconds if self.total_workout_seconds > 0 else 0
        
        self.workout_timer_widget.update_progress(
            workout_progress,
            f"{elapsed_minutes:02d}:{elapsed_seconds_rem:02d}",
            f"Workout ({total_minutes:02d}:{total_seconds_rem:02d})"
        )

    def update_exercise_timer_display(self):
        remaining_seconds = self.exercise_timer
        remaining_minutes = remaining_seconds // 60
        remaining_secs = remaining_seconds % 60
        
        exercise_progress = 1 - (remaining_seconds / self.initial_exercise_time) if self.initial_exercise_time > 0 else 0
        
        self.exercise_timer_widget.update_progress(
            exercise_progress, 
            f"{remaining_minutes:02d}:{remaining_secs:02d}", 
            "Exercise Left"
        )

    def update_workout_time(self, dt):
        self.elapsed_workout_seconds += 1
        if self.elapsed_workout_seconds > self.total_workout_seconds:
            self.elapsed_workout_seconds = self.total_workout_seconds
        self.update_workout_time_display()
        if self.elapsed_workout_seconds >= self.total_workout_seconds:
            self.show_completion()

    def start_next_exercise(self):
        if self.current_index >= len(self.exercises):
            self.show_completion()
            return

        self.instructions_box.clear_widgets()
        self.video_player.state = 'stop'
        self.video_player.source = ''
        
        exercise = self.exercises[self.current_index]

        if exercise["id"] == -1:
            self.start_break_timer(exercise)
            return

        # (This code now only runs if it's NOT a break)
        self.exercise_label.text = exercise["name"].upper()
        self.progress_label.text = f"Exercise {self.current_index + 1} of {len(self.exercises)}"
        
        instructions = exercise["instructions"].split('\n')
        
        for inst_line in instructions:
            if inst_line.strip():
                self.instructions_box.add_widget(
                    MDLabel(
                        text=f"• {inst_line.strip()}",
                        halign='left',
                        theme_text_color="Custom",
                        text_color=COLORS["instructions_text"],
                        size_hint_y=None,
                        adaptive_height=True,
                        text_size=(self.instructions_box.width - dp(20), None) 
                    )
                )
        if self.instructions_box.parent:
            self.instructions_box.parent.scroll_y = 1

        # Format video file name
        video_name = exercise["name"].lower().replace(" ", "_")
        video_file = f"vids/{video_name}.mp4" 

        self.video_container.clear_widgets()
        if os.path.exists(video_file):
            self.video_player.source = video_file
            self.video_player.state = 'play'
            self.video_container.add_widget(self.video_player)
        else:
            print(f"Video file not found: {video_file}")
            self.video_container.add_widget(self.video_not_found_label)
        
        # Get duration (in minutes) and convert to seconds
        self.exercise_timer = exercise["duration"] * 60
        self.initial_exercise_time = self.exercise_timer
        self.update_exercise_timer_display()

        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_exercise_timer, 1)

    def update_exercise_timer(self, dt):
        self.exercise_timer -= 1
        self.update_exercise_timer_display()
        if self.exercise_timer <= 0:
            self.current_index += 1
            self.start_next_exercise()

    def stop_timers(self):
        self.video_player.state = 'stop'
        self.video_player.source = ''
        if self.timer_event:
            self.timer_event.cancel()
            self.timer_event = None
        if self.workout_timer_event:
            self.workout_timer_event.cancel()
            self.workout_timer_event = None

    def end_workout_dialog(self, *args):
        self.app.dialog = MDDialog(
            title="End Workout?",
            text="Are you sure you want to end this workout? Your progress will be saved.",
            buttons=[
                MDTextButton(text="CANCEL", on_release=self.app.close_dialog),
                MDRaisedButton(text="END", md_bg_color=COLORS["error"], on_release=self.end_workout_confirmed),
            ],
        )
        self.app.dialog.open()

    def end_workout_confirmed(self, *args):
        self.app.close_dialog()
        self.stop_timers()
        self.app.log_and_exit_workout(
            self.elapsed_workout_seconds,
            self.training_plan.name
        )
        self.app.root.ids.screen_manager.current = 'home'

    def go_to_home(self, *args):
        if hasattr(self.app.root, 'ids') and 'screen_manager' in self.app.root.ids:
             self.app.root.ids.screen_manager.current = 'home'
        else:
             print("Error: Could not switch screen, ScreenManager not found.")

    def show_completion(self):
        self.stop_timers()
        
        # Log the workout
        self.app.log_and_exit_workout(
            self.elapsed_workout_seconds, 
            self.training_plan.name,
            no_redirect=True
        )
        
        # Show completion screen
        actual_minutes = self.elapsed_workout_seconds // 60
        actual_seconds = self.elapsed_workout_seconds % 60
        self.stats_label.text = f"Total Time: {actual_minutes}:{actual_seconds:02d}\nGreat job!"
        
        if self.main_layout.parent == self:
            self.remove_widget(self.main_layout)
        if self.completion_layout.parent != self:
             self.add_widget(self.completion_layout)

    def start_break_timer(self, break_exercise):
        """Shows a 1-minute break screen."""
        self.exercise_label.text = "BREAK TIME"
        self.progress_label.text = "Rest and hydrate!"
        
        # Clear instructions
        self.instructions_box.clear_widgets()
        self.instructions_box.add_widget(
            MDLabel(
                text="• Take a 1-minute break.\n• Drink some water.\n• Prepare for the next exercise.",
                halign='left',
                theme_text_color="Custom",
                text_color=COLORS["instructions_text"],
                size_hint_y=None,
                adaptive_height=True,
                text_size=(self.instructions_box.width - dp(20), None)
            )
        )

        # Stop video and show a "resting" label
        self.video_player.state = 'stop'
        self.video_player.source = ''
        self.video_container.clear_widgets()
        self.video_container.add_widget(
            MDLabel(
                text="Resting... 🧘",
                font_style='H4',
                halign='center',
                theme_text_color="Secondary"
            )
        )
        
        # Set timer (duration is in minutes, convert to seconds)
        self.exercise_timer = break_exercise["duration"] * 60
        self.initial_exercise_time = self.exercise_timer
        self.update_exercise_timer_display()

        # Start the countdown timer
        if self.timer_event:
            self.timer_event.cancel()
        self.timer_event = Clock.schedule_interval(self.update_exercise_timer, 1)
class CalendarDayButton(RectangularRippleBehavior, ButtonBehavior, MDAnchorLayout):
    text = StringProperty()
    circle_bg_color = ColorProperty([0, 0, 0, 0])
    text_color = ColorProperty([1, 1, 1, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(circle_bg_color=self.update_canvas, pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.circle_bg_color)
            Ellipse(size=self.size, pos=self.pos)

class WorkoutCard(MDCard):
    workout_name = StringProperty()
    description = StringProperty()
    duration = StringProperty()
    difficulty = StringProperty()
    workout_data = ObjectProperty()
    
    def on_release(self):
        app = MDApp.get_running_app()
        app.show_workout_detail(self.workout_data)

class WorkoutDetailContent(MDBoxLayout):
    pass

class PlanListItem(OneLineListItem):
    plan_name = StringProperty()
    
    def __init__(self, plan_data, **kwargs):
        super().__init__(**kwargs)
        self.plan_data = plan_data
        self.plan_name = f"Plan from {plan_data.get('generated_date', 'Unknown')}"

    def view_plan(self):
        app = MDApp.get_running_app()
        app.view_saved_plan(self.plan_data)
        
class AddTrainingDialog(MDBoxLayout):
    """
    This class is the content for the 'Add New Training Plan' dialog.
    The layout is defined in the <AddTrainingDialog> rule in your KV file.
    """
    pass

# --- AI Plan Generator ---
class PlanGenerator:
    def __init__(self, use_gemini=True, api_key=None):
        self.use_gemini = use_gemini
        self.api_key = api_key
        self.gemini_working = False
        self.model = None
        
        if use_gemini and GEMINI_AVAILABLE and api_key and api_key != "YOUR_GEMINI_API_KEY_HERE":
            try:
                genai.configure(api_key=api_key)
                model_name = 'models/gemini-2.0-flash'
                try:
                    self.model = genai.GenerativeModel(model_name)
                    test_response = self.model.generate_content("Test connection")
                    if test_response.text:
                        self.gemini_working = True
                except Exception as e:
                    print(f"❌ Failed to initialize {model_name}: {e}")
                    self.gemini_working = False
                    
            except Exception as e:
                print(f"❌ Failed to configure Gemini: {e}")
                self.gemini_working = False
        else:
            self.gemini_working = False
            if not GEMINI_AVAILABLE:
                print("❌ Google Generative AI not installed")
            elif not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
                print("❌ Invalid API key")
        
    def generate_personalized_plan(self, user_data):
        if self.use_gemini and self.gemini_working:
            try:
                plan = self._generate_ai_plan(user_data)
                return plan
            except Exception as e:
                print(f"❌ AI Generation Failed: {e}")
                return self._create_fallback_plan(user_data)
        else:
            return self._create_fallback_plan(user_data)

    def _generate_ai_plan(self, user_data):
        """Generate plan using Gemini AI"""
        try:
            prompt = self._create_ai_prompt(user_data)
            response = self.model.generate_content(prompt)
            plan_text = response.text
            parsed_plan = self._parse_ai_response(plan_text)
            
            return {
                'user_data': user_data,
                'nutrition_plan': parsed_plan.get('nutrition_plan', 'Nutrition plan not generated.'),
                'workout_plan': parsed_plan.get('workout_plan', 'Workout plan not generated.'),
                'important_notes': parsed_plan.get('important_notes', 'Important notes not generated.'),
                'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'ai_generated': True
            }
        except Exception as e:
            print(f" AI plan generation error: {e}")
            raise

    def _create_ai_prompt(self, user_data):
        conditions_text = ", ".join(user_data['health_conditions']) if user_data['health_conditions'] else "None"
        weight_diff = user_data['current_weight'] - user_data['goal_weight']
        bmi = user_data['current_weight'] / ((user_data['height']/100) ** 2)
        
        return f"""
        Create a COMPREHENSIVE fitness and nutrition plan. You MUST include ALL THREE sections below.

        USER DETAILS:
        - Age: {user_data['age']} years
        - Gender: {user_data['gender']}
        - Height: {user_data['height']} cm
        - Current Weight: {user_data['current_weight']} kg
        - Goal Weight: {user_data['goal_weight']} kg
        - Weight to lose/gain: {weight_diff:.1f} kg
        - BMI: {bmi:.1f}
        - Timeline: {user_data['goal_time_weeks']} weeks
        - Activity: {user_data['activity_level']}
        - Goal: {user_data['primary_goal']}
        - Diet: {user_data['diet_preference']}
        - Budget: {user_data['budget_level']}
        - Health Conditions: {conditions_text}

        CRITICAL: You MUST format your response EXACTLY like this:

        NUTRITION PLAN:
        [Provide a detailed daily meal plan here. Include:
        - Specific foods and portions for breakfast, lunch, dinner, snacks
        - Calorie targets and macronutrient breakdown
        - Meal timing and preparation tips
        - Foods suitable for {user_data['diet_preference']} diet and {user_data['budget_level']} budget]

        WORKOUT PLAN:
        [Provide a detailed weekly exercise routine here. Include:
        - Specific exercises with sets, reps, and duration
        - Weekly schedule (Monday to Sunday)
        - Warm-up and cool-down routines
        - Progression plan and intensity levels
        - Age-appropriate exercises for {user_data['age']} years]

        IMPORTANT NOTES:
        [Provide safety considerations and advice here. Include:
        - Health condition modifications for {conditions_text}
        - Progress tracking methods
        - Warning signs to watch for
        - When to consult healthcare professionals
        - Hydration and recovery advice]

        Make it highly personalized, practical, and safe .
        """

    def _parse_ai_response(self, plan_text):
        """Improved parsing to handle different AI response formats"""
        sections = {
            'nutrition_plan': '',
            'workout_plan': '',
            'important_notes': ''
        }
        
        text_upper = plan_text.upper()
        
        nutrition_start = text_upper.find('NUTRITION PLAN:')
        workout_start = text_upper.find('WORKOUT PLAN:')
        notes_start = text_upper.find('IMPORTANT NOTES:')
        
        if nutrition_start != -1 and workout_start != -1 and notes_start != -1:
            sections['nutrition_plan'] = plan_text[nutrition_start:workout_start].strip()
            sections['workout_plan'] = plan_text[workout_start:notes_start].strip()
            sections['important_notes'] = plan_text[notes_start:].strip()
        else:
            lines = plan_text.split('\n')
            current_section = None
            
            for line in lines:
                line_upper = line.upper().strip()
                
                if 'NUTRITION' in line_upper and ('PLAN' in line_upper or 'DIET' in line_upper):
                    current_section = 'nutrition_plan'
                    sections[current_section] += line + '\n'
                elif 'WORKOUT' in line_upper or 'EXERCISE' in line_upper or 'FITNESS' in line_upper:
                    current_section = 'workout_plan'
                    sections[current_section] += line + '\n'
                elif 'IMPORTANT' in line_upper or 'NOTES' in line_upper or 'SAFETY' in line_upper:
                    current_section = 'important_notes'
                    sections[current_section] += line + '\n'
                elif current_section and line.strip():
                    sections[current_section] += line + '\n'
        
        for section_name in sections:
            if not sections[section_name].strip():
                if section_name == 'nutrition_plan':
                    sections[section_name] = "Nutrition plan details not provided by AI. Please ensure you include specific meal plans in your response."
                elif section_name == 'workout_plan':
                    sections[section_name] = "Workout plan details not provided by AI. Please ensure you include specific exercise routines in your response."
                elif section_name == 'important_notes':
                    sections[section_name] = "Important notes not provided by AI."
        
        return sections

    def _create_fallback_plan(self, user_data):
        """Simple fallback if AI fails"""
        return {
            'user_data': user_data,
            'nutrition_plan': "AI generation failed. Please try again later.",
            'workout_plan': "AI generation failed. Please try again later.",
            'important_notes': "AI generation failed. Please try again later.",
            'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'ai_generated': False
        }

# --- MAIN APP CLASS ---

class ComprehensiveFitnessApp(MDApp):
    DB_NAME = "fitmate.db"
    current_date = date.today()
    workout_dates = set()
    weight_data = {}  
    current_filter = "All"
    current_training_plan = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = 1
        self.workout_library = []
        self.my_workouts = []
        self.dialog = None
        self.current_plan = None
        self.selected_training_id = None

        # AI Configuration
        self.GEMINI_API_KEY = "AIzaSyCzQwoXTTO_W50bTALOiyNh5k5TNKXtoRQ"
        self.plan_generator = None
        
        # Personalization data
        self.selected_conditions = []
        self.selected_gender = ""
        self.activity_level = ""
        self.primary_goal = ""
        self.diet_preference = ""
        self.budget_level = ""
        
        self.health_conditions = [
            "Diabetes", "High Blood Pressure", "Heart Disease", "Arthritis",
            "Asthma", "Osteoporosis", "Back Pain", "Knee Problems",
            "Obesity", "Thyroid Issues", "PCOS", "High Cholesterol",
            "Joint Pain", "Migraine", "Anxiety/Depression", "None"
        ]
        
        self.genders = ["Male", "Female", "Other"]
        self.activity_levels = ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"]
        self.fitness_goals = ["Weight Loss", "Muscle Gain", "Maintenance", "Improve Fitness", "Rehabilitation"]
        self.diet_preferences = ["Vegetarian", "Non-Vegetarian", "Vegan", "Mixed Diet"]
        self.budget_levels = ["Low Budget", "Medium Budget", "High Budget"]
        
        self.load_sample_workouts()
        self.initialize_plan_generator()

    def initialize_plan_generator(self):
        self.plan_generator = PlanGenerator(use_gemini=True, api_key=self.GEMINI_API_KEY)

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        return Builder.load_string(KV)

    def on_start(self):
        self.init_db()
        self.setup_user()
        
        # --- 1. Get UI elements from KV file ---
        self.user_dropdown = self.root.ids.user_dropdown_item
        drawer_content = self.root.ids.drawer_content

        # --- 2. Create the Calendar UI first ---
        self.calendar_view = self.create_calendar_view()
        drawer_content.add_widget(self.calendar_view)

        # --- 3. Now that UI exists, load data ---
        self.load_user_data() 

        # --- 4. Build the menus ---
        self.build_user_menu()
        
        # Setup training dropdown
        self.dropdown_item = self.root.ids.dropdown_item
        self.dropdown_item.set_item("Select")
        training_plans_dict = self.get_all_training_types_as_dict()
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": name,
                "on_release": lambda x=name, y=uid: self.menu_callback((x, y)),
            }
            for name, uid in training_plans_dict.items()
        ]
        self.menu = MDDropdownMenu(caller=self.dropdown_item, items=menu_items, width_mult=5)
        
        self.filter_menu_items = [
            {"text": "All Levels", "viewclass": "OneLineListItem", "on_release": lambda x="All": self.filter_menu_callback(x)},
            {"text": "Beginner", "viewclass": "OneLineListItem", "on_release": lambda x="Beginner": self.filter_menu_callback(x)},
            {"text": "Intermediate", "viewclass": "OneLineListItem", "on_release": lambda x="Intermediate": self.filter_menu_callback(x)},
            {"text": "Advanced", "viewclass": "OneLineListItem", "on_release": lambda x="Advanced": self.filter_menu_callback(x)},
        ]
        
        # --- 5. Add other UI elements ---
        self.add_weight_entry_ui()
        self.display_workouts(self.workout_library)

    def open_menu(self, *args):
        """Opens the main training plan dropdown menu."""
        self.menu.open()

    # --- Database Methods ---
    def init_db(self):
        conn = sqlite3.connect(self.DB_NAME)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        
        cur.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cur.execute("CREATE TABLE IF NOT EXISTS workouts(workout_id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, duration INTEGER, calories INTEGER, date TEXT, FOREIGN KEY(user_id) REFERENCES users(user_id))")
        cur.execute("CREATE TABLE IF NOT EXISTS streaks(user_id INTEGER PRIMARY KEY, current_streak INTEGER, longest_streak INTEGER, last_workout_date TEXT, FOREIGN KEY(user_id) REFERENCES users(user_id))")
        cur.execute("CREATE TABLE IF NOT EXISTS weights(id INTEGER PRIMARY KEY, user_id INTEGER, weight REAL, date TEXT, FOREIGN KEY(user_id) REFERENCES users(user_id))")
        
        # AI Plan tables
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_data TEXT,
                created_date TEXT
            )
        ''')
        
        # Training tables
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exercise_type (
            unique_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, instructions TEXT
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS training_types (
            unique_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, exercise_ids TEXT 
        )""")
        
        conn.commit()
        conn.close()

    def get_all_training_types_as_dict(self):
        """Fetches a list of all training plans from the training_types table."""
        query = "SELECT name, unique_id FROM training_types ORDER BY name"
        records = self.db_fetch(query)
        return {name: uid for name, uid in records}

    # --- Training Methods ---
    def menu_callback(self, training_data):
        training_name, training_id = training_data
        self.dropdown_item.set_item(training_name)
        self.selected_training_id = training_id
        self.menu.dismiss()

    def start_training(self):
        if self.selected_training_id is None:
            toast("Please select a training plan first")
            return
        
        # Load the selected training plan
        self.current_training_plan = Training(self.selected_training_id, self.DB_NAME)
        if not self.current_training_plan.name:
            toast("Error: Could not load training plan")
            print(f"❌ Failed to load training plan with ID: {self.selected_training_id}")
            return

        # Check if we have exercises
        if not self.current_training_plan.exercises:
            toast("No exercises found in this training plan!")
            print(f"❌ No exercises found for training plan: {self.current_training_plan.name}")
            return

        # Get the workout screen and start it
        workout_screen = self.root.ids.screen_manager.get_screen('workout')
        workout_screen.start_new_workout(self.current_training_plan)
        
        # Switch to the workout screen
        self.root.ids.screen_manager.current = 'workout'
        toast(f"Starting {self.current_training_plan.name}!")
    
    def log_and_exit_workout(self, total_seconds_completed, plan_name, no_redirect=False):
        total_duration_minutes = total_seconds_completed // 60
        if total_duration_minutes == 0 and total_seconds_completed > 0:
            total_duration_minutes = 1 
        estimated_calories = total_duration_minutes * random.randint(5, 8)

        # Add to database
        if total_duration_minutes > 0:
            self.add_workout_record(
                self.user_id,
                plan_name,
                total_duration_minutes,
                estimated_calories
            )
            toast(f"Logged '{plan_name}' workout!")
        else:
            toast("Workout too short to log.")
        
        # Update UI
        self.workout_dates = self.get_workout_dates(self.user_id)
        try:
            if self.root.ids.screen_manager.current == 'home' and 'graph_box' in self.root.ids:
                self.populate_calendar()
            else:
                self.populate_calendar()
        except Exception as e:
            print(f"Error updating UI after workout: {e}")

    # --- DB Helper Methods ---
    def db_execute(self, query, params=()):
        conn = sqlite3.connect(self.DB_NAME)
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        conn.close()

    def db_fetch(self, query, params=()):
        conn = sqlite3.connect(self.DB_NAME)
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows

    def setup_user(self):
        users = self.db_fetch("SELECT * FROM users WHERE user_id = ?", (self.user_id,))
        if not users:
            self.db_execute("INSERT INTO users(user_id, name) VALUES (?, ?)", (self.user_id, "Default User"))
            self.db_execute("INSERT INTO streaks(user_id, current_streak, longest_streak) VALUES (?, ?, ?)", (self.user_id, 0, 0))

    def add_workout_record(self, user_id, workout_type, duration, calories):
        date_today = datetime.now().strftime("%Y-%m-%d")
        self.db_execute("INSERT INTO workouts(user_id, type, duration, calories, date) VALUES (?, ?, ?, ?, ?)", (user_id, workout_type, duration, calories, date_today))

    def add_weight_record(self, user_id, weight):
        date_today = datetime.now().strftime("%Y-%m-%d")
        self.db_execute("INSERT INTO weights(user_id, weight, date) VALUES (?, ?, ?)", (user_id, weight, date_today))

    def get_weight_records(self, user_id, limit=7):
        return self.db_fetch("SELECT date, weight FROM weights WHERE user_id = ? ORDER BY date DESC LIMIT ?", (user_id, limit))

    def get_all_weight_data(self):
        records = self.db_fetch("SELECT date, weight FROM weights WHERE user_id = ? ORDER BY date", (self.user_id,))
        return {rec[0]: rec[1] for rec in records}

    def get_workout_records(self, user_id, limit=7):
        query = "SELECT date, SUM(calories), SUM(duration) FROM workouts WHERE user_id = ? GROUP BY date ORDER BY date DESC LIMIT ?"
        return self.db_fetch(query, (user_id, limit))
        
    def get_workout_dates(self, user_id):
        records = self.db_fetch("SELECT DISTINCT date FROM workouts WHERE user_id = ?", (user_id,))
        return {datetime.strptime(rec[0], "%Y-%m-%d").date() for rec in records}

    def load_sample_workouts(self):
        self.workout_library = [
            # Existing Workouts (Expanded Descriptions)
            {'name': '3-Day Full Body Split', 'description': 'Complete full body strength workout spread across 3 days for muscle gain and maintenance.', 'duration': '45-60 mins', 'difficulty': 'Beginner', 'days_per_week': '3', 'exercises': [{'name': 'Squats', 'sets': '3', 'reps': '10-12'}, {'name': 'Bench Press', 'sets': '3', 'reps': '8-10'}, {'name': 'Bent-over Rows', 'sets': '3', 'reps': '8-10'}, {'name': 'Lunges', 'sets': '3', 'reps': '10-12 each'}]},
            {'name': 'Beginner Abs', 'description': 'Fundamental core workout for beginners focusing on basic stability and strength.', 'duration': '20-30 mins', 'difficulty': 'Beginner', 'days_per_week': '3-4', 'exercises': [{'name': 'Crunches', 'sets': '3', 'reps': '15-20'}, {'name': 'Leg Raises', 'sets': '3', 'reps': '12-15'}, {'name': 'Plank', 'sets': '3', 'reps': '30-45 sec'}]},
            {'name': 'At-Home Cardio', 'description': 'No-equipment high-energy cardio workout to boost heart rate and burn calories.', 'duration': '30-40 mins', 'difficulty': 'Intermediate', 'days_per_week': '4-5', 'exercises': [{'name': 'Jumping Jacks', 'sets': '4', 'reps': '45 sec'}, {'name': 'High Knees', 'sets': '4', 'reps': '45 sec'}, {'name': 'Burpees', 'sets': '4', 'reps': '12-15'}]},
            {'name': 'Upper Body Strength', 'description': 'Build strong arms, chest and back using bodyweight or light dumbbells.', 'duration': '50-60 mins', 'difficulty': 'Intermediate', 'days_per_week': '3', 'exercises': [{'name': 'Bench Press', 'sets': '4', 'reps': '8-10'}, {'name': 'Pull-ups', 'sets': '3', 'reps': '6-8'}, {'name': 'Shoulder Press', 'sets': '3', 'reps': '8-10'}]},
            
            # YOGA & PILATES
            {'name': 'Morning Mobility Flow', 'description': 'Gentle Hatha-based yoga to increase flexibility, improve posture, and prepare the body for the day.', 'duration': '20 mins', 'difficulty': 'Beginner', 'days_per_week': '5-7', 'exercises': [{'name': 'Cat-Cow', 'sets': '1', 'reps': '10 reps'}, {'name': 'Downward Dog', 'sets': '1', 'reps': '1 min hold'}, {'name': 'Cobra Pose', 'sets': '1', 'reps': '30 sec hold'}, {'name': 'Child\'s Pose', 'sets': '1', 'reps': '1 min hold'}]},
            {'name': 'Power Vinyasa', 'description': 'A strong, flowing intermediate yoga practice for building heat, endurance, and strength.', 'duration': '45 mins', 'difficulty': 'Intermediate', 'days_per_week': '3', 'exercises': [{'name': 'Sun Salutations', 'sets': '3', 'reps': '1 set'}, {'name': 'Warrior II Flow', 'sets': '1', 'reps': '1 min/side'}, {'name': 'Crow Pose Prep', 'sets': '3', 'reps': '15 sec hold'}]},
            {'name': 'Advanced Pilates Core', 'description': 'Challenging Pilates routine focusing on deep core muscles, control, and breathwork.', 'duration': '30 mins', 'difficulty': 'Advanced', 'days_per_week': '3-4', 'exercises': [{'name': 'The Hundred', 'sets': '1', 'reps': '100 breaths'}, {'name': 'Teaser', 'sets': '3', 'reps': '10 reps'}, {'name': 'Jackknife', 'sets': '3', 'reps': '8 reps'}]},
            
            # HIIT (High-Intensity Interval Training)
            {'name': 'HIIT Express 15', 'description': 'Short but intense workout: 30 seconds work, 15 seconds rest.', 'duration': '15 mins', 'difficulty': 'Intermediate', 'days_per_week': '3-5', 'exercises': [{'name': 'Squat Jumps', 'sets': '3', 'reps': '30 sec'}, {'name': 'Mountain Climbers', 'sets': '3', 'reps': '30 sec'}, {'name': 'Push-ups', 'sets': '3', 'reps': '30 sec'}, {'name': 'Burpees', 'sets': '3', 'reps': '30 sec'}]},
            {'name': 'Tabata Destroyer', 'description': 'Maximum intensity Tabata intervals (20s work, 10s rest) for extreme calorie burn.', 'duration': '25 mins', 'difficulty': 'Advanced', 'days_per_week': '3', 'exercises': [{'name': 'Box Jumps', 'sets': '8', 'reps': '20/10 sec'}, {'name': 'Kettlebell Swings', 'sets': '8', 'reps': '20/10 sec'}, {'name': 'Sprints', 'sets': '8', 'reps': '20/10 sec'}]},
            
            # CARDIO & ENDURANCE
            {'name': 'Steady-State Endurance', 'description': 'Classic continuous cardio work (e.g., running, cycling) for cardiovascular health and fat loss.', 'duration': '40-60 mins', 'difficulty': 'Intermediate', 'days_per_week': '3-4', 'exercises': [{'name': 'Outdoor Run', 'sets': '1', 'reps': '45 mins'}, {'name': 'Cool Down Stretch', 'sets': '1', 'reps': '5 mins'}]},
            
            # STRENGTH & BODYBUILDING
            {'name': 'Leg Day - Hypertrophy', 'description': 'Volume-based leg workout designed for maximum muscle growth and strength development.', 'duration': '60-75 mins', 'difficulty': 'Advanced', 'days_per_week': '1-2', 'exercises': [{'name': 'Heavy Squats', 'sets': '4', 'reps': '6-8'}, {'name': 'Romanian Deadlifts', 'sets': '3', 'reps': '10-12'}, {'name': 'Leg Extensions', 'sets': '3', 'reps': '12-15'}]},
            {'name': 'Upper Body Maintenance', 'description': 'A quick strength routine for maintaining muscle mass on a busy schedule.', 'duration': '30-40 mins', 'difficulty': 'Intermediate', 'days_per_week': '2', 'exercises': [{'name': 'Incline Dumbbell Press', 'sets': '3', 'reps': '8-10'}, {'name': 'Dumbbell Rows', 'sets': '3', 'reps': '8-10'}, {'name': 'Bicep Curls', 'sets': '3', 'reps': '10-12'}]},
        ]

    # --- Navigation Methods ---
    def switch_to_home(self):
        self.root.ids.screen_manager.current = "home"
        self.root.ids.nav_drawer.set_state("close")

    def switch_to_history(self):
        self.root.ids.screen_manager.current = "history"
        self.root.ids.nav_drawer.set_state("close")
        self.populate_history_list()

    def populate_history_list(self):
        """Fetches and displays the workout history for the current user."""
        history_list = self.root.ids.history_list
        history_list.clear_widgets()
        
        try:
            workouts = self.db_fetch(
                "SELECT type, date, duration, calories FROM workouts WHERE user_id = ? ORDER BY date DESC",
                (self.user_id,)
            )
            
            if not workouts:
                history_list.add_widget(
                    OneLineListItem(text="No workout history found.")
                )
                return
            for workout_type, date_str, duration, calories in workouts:
                primary_text = f"{workout_type}"
                secondary_text = f"{date_str}  -  {duration} mins, {calories} kcal"
                
                list_item = TwoLineListItem(
                    text=primary_text,
                    secondary_text=secondary_text
                )
                history_list.add_widget(list_item)
                
        except Exception as e:
            print(f"Error populating history: {e}")
            history_list.add_widget(
                OneLineListItem(text="Error loading history.")
            )

    def switch_to_workout_library(self):
        self.root.ids.screen_manager.current = "workout_library"
        self.root.ids.nav_drawer.set_state("close")

    def switch_to_personalization(self):
        self.root.ids.screen_manager.current = "personalization"
        self.root.ids.nav_drawer.set_state("close")

    def switch_to_saved_plans(self):
        self.root.ids.screen_manager.current = "saved_plans"
        self.root.ids.nav_drawer.set_state("close")
        self.display_saved_plans()

    def switch_to_plan_display(self, plan_data=None):
        if plan_data:
            self.display_ai_plan(plan_data)
        self.root.ids.screen_manager.current = "plan_display"

    # --- Calendar and Graph Methods ---
    def create_calendar_view(self):
        calendar_layout = MDBoxLayout(orientation='vertical', adaptive_height=True, size_hint_x=1, spacing=dp(10))
        
        header = MDBoxLayout(adaptive_height=True, padding=(0, dp(10), 0, dp(10)))
        self.month_year_label = MDLabel(halign='center', font_style='H6')
        prev_button = MDIconButton(icon='chevron-left', on_release=partial(self.change_month, -1))
        next_button = MDIconButton(icon='chevron-right', on_release=partial(self.change_month, 1))
        header.add_widget(prev_button)
        header.add_widget(self.month_year_label)
        header.add_widget(next_button)
        
        days_header = MDGridLayout(cols=7, adaptive_height=True)
        for day in ["M", "Tu", "W", "Th", "F", "Sa", "Su"]:
            days_header.add_widget(MDLabel(text=day, halign='center', color=self.theme_cls.disabled_hint_text_color))
            
        self.days_grid = MDGridLayout(cols=7, adaptive_height=True, spacing=dp(4), padding=dp(4))
        
        calendar_layout.add_widget(header)
        calendar_layout.add_widget(days_header)
        calendar_layout.add_widget(self.days_grid)
        return calendar_layout

    def populate_calendar(self):
        self.days_grid.clear_widgets()
        self.month_year_label.text = self.current_date.strftime("%B %Y")
        month_weeks = calendar.monthcalendar(self.current_date.year, self.current_date.month)
        today = date.today()

        for week in month_weeks:
            for day in week:
                if day == 0:
                    self.days_grid.add_widget(Widget())
                else:
                    day_date = date(self.current_date.year, self.current_date.month, day)
                    day_button = CalendarDayButton(text=str(day))
                    day_button.text_color = self.theme_cls.text_color
                    
                    if day_date in self.workout_dates:
                        day_button.circle_bg_color = (1, 1, 0, 0.4)
                    
                    if day_date == today:
                        day_button.text_color = self.theme_cls.primary_color
                        if day_date not in self.workout_dates:
                            day_button.circle_bg_color = (*self.theme_cls.primary_color[:3], 0.2)
                    
                    self.days_grid.add_widget(day_button)

    def change_month(self, month_offset, *args):
        new_month = self.current_date.month + month_offset
        new_year = self.current_date.year
        if new_month > 12:
            new_month = 1
            new_year += 1
        elif new_month < 1:
            new_month = 12
            new_year -= 1
        self.current_date = date(new_year, new_month, 1)
        self.populate_calendar()

    def add_weight_entry_ui(self):
        weight_box = MDBoxLayout(orientation='vertical', adaptive_height=True, spacing=dp(10), padding=(dp(20), dp(20), dp(20), dp(40)))
        weight_label = MDLabel(text="Log Your Weight (kg)", halign="center", font_style="H6")
        self.weight_input = MDTextField(hint_text="Enter weight", input_filter="float", halign="center")
        save_button = MDRaisedButton(text="SAVE WEIGHT", on_release=self.save_weight, pos_hint={'center_x': 0.5})
        weight_box.add_widget(weight_label)
        weight_box.add_widget(self.weight_input)
        weight_box.add_widget(save_button)
        self.root.ids.drawer_content.add_widget(weight_box)

    def save_weight(self, *args):
        try:
            weight = float(self.weight_input.text)
            self.add_weight_record(self.user_id, weight)
            toast(f"Weight saved: {weight} kg")
            self.weight_input.text = ""
        
            self.weight_data = self.get_all_weight_data()
            self.populate_calendar()
            
            if self.root.ids.graph_dropdown.text == "Weight Progress":
                self.show_weekly_progress("Weight Progress")
        except ValueError:
            toast("Please enter a valid weight")

    def open_graph_menu(self):
        graph_dropdown = self.root.ids.graph_dropdown
        menu_items = [
            {"text": item, "viewclass": "OneLineListItem", "on_release": lambda x=item: self.graph_menu_callback(x)}
            for item in ["Calories Burned", "Weight Progress", "Workout Duration"]
        ]
        self.graph_menu = MDDropdownMenu(caller=graph_dropdown, items=menu_items, width_mult=4)
        self.graph_menu.open()

    def graph_menu_callback(self, graph_type):
        self.root.ids.graph_dropdown.set_item(graph_type)
        self.graph_menu.dismiss()
        self.show_weekly_progress(graph_type)

    def show_weekly_progress(self, graph_type="Calories Burned"):
        plt.clf()
        fig, ax = plt.subplots(figsize=(5, 3), facecolor=self.theme_cls.bg_dark)
        ax.set_facecolor(self.theme_cls.bg_dark)
        
        ax.grid(axis='y', linestyle='--', alpha=0.4, color='white')
        ax.tick_params(axis='x', colors='white', rotation=20)
        ax.tick_params(axis='y', colors='white')

        if graph_type == "Weight Progress":
            ylabel, color = "Weight (kg)", 'orange'
            records = self.get_weight_records(self.user_id, limit=7)
            records.reverse()
            if records:
                days = [datetime.strptime(rec[0], "%Y-%m-%d").strftime("%b %d") for rec in records]
                y = [rec[1] for rec in records]
                ax.plot(days, y, color=color, marker='o', linestyle='-')
                ax.fill_between(days, y, color=color, alpha=0.2)
                
                if len(y) > 1:
                    min_weight = min(y)
                    max_weight = max(y)
                    ax.set_ylim([min_weight - 1, max_weight + 1])

                for i, (day, weight) in enumerate(zip(days, y)):
                    ax.annotate(f'{weight:.1f}', (day, weight), textcoords="offset points", xytext=(0,10), ha='center', color='white')
            else:
                ax.text(0.5, 0.5, 'No Weight Data', transform=ax.transAxes, ha='center', va='center', color='white', fontsize=12)
        
        elif graph_type in ["Calories Burned", "Workout Duration"]:
            records = self.get_workout_records(self.user_id, limit=7)
            records.reverse()

            if graph_type == "Calories Burned":
                ylabel, color, data_index = "Calories (kcal)", 'teal', 1
            else:
                ylabel, color, data_index = "Duration (mins)", 'green', 2

            if records:
                days = [datetime.strptime(rec[0], "%Y-%m-%d").strftime("%b %d") for rec in records]
                y = [rec[data_index] if rec[data_index] is not None else 0 for rec in records]
                ax.plot(days, y, color=color, marker='o', linestyle='-')
                ax.fill_between(days, y, color=color, alpha=0.2)

                for i, (day, value) in enumerate(zip(days, y)):
                    ax.annotate(f'{int(value)}', (day, value), textcoords="offset points", xytext=(0,10), ha='center', color='white')
            else:
                ax.text(0.5, 0.5, 'No Workout Data', transform=ax.transAxes, ha='center', va='center', color='white', fontsize=12)

        ax.set_ylabel(ylabel, color='white')
        
        fig.tight_layout()

        graph_box = self.root.ids.graph_box
        graph_box.clear_widgets()
        graph_box.add_widget(FigureCanvasKivyAgg(fig))

    # --- Workout Library Methods ---
    def open_filter_menu(self):
        self.filter_menu = MDDropdownMenu(
            caller=self.root.ids.workout_library_top_bar,
            items=self.filter_menu_items,
            width_mult=4
        )
        self.filter_menu.open()

    def filter_menu_callback(self, difficulty_level):
        self.filter_menu.dismiss()
        self.current_filter = difficulty_level
        
        if difficulty_level == "All":
            filtered_workouts = self.workout_library
            message = "Showing all workouts"
        else:
            filtered_workouts = [w for w in self.workout_library if w['difficulty'] == difficulty_level]
            message = f"Showing {difficulty_level} workouts"
        
        self.display_workouts(filtered_workouts)
        toast(message)
        
    def display_workouts(self, workouts):
        workout_list = self.root.ids.workout_list
        workout_list.clear_widgets()
        for workout in workouts:
            card = WorkoutCard(
                workout_name=workout['name'],
                description=workout['description'],
                duration=workout['duration'],
                difficulty=workout['difficulty'],
                workout_data=workout
            )
            workout_list.add_widget(card)
        
        workout_list.height = len(workouts) * dp(150)

    def filter_workouts(self, search_text):
        if search_text:
            filtered = [w for w in self.workout_library if search_text.lower() in w['name'].lower() or search_text.lower() in w['description'].lower()]
            self.display_workouts(filtered)
        else:
            if self.current_filter == "All":
                self.display_workouts(self.workout_library)
            else:
                filtered = [w for w in self.workout_library if w['difficulty'] == self.current_filter]
                self.display_workouts(filtered)

    def show_workout_detail(self, workout_data):
        content = WorkoutDetailContent()

        title_box = MDBoxLayout(adaptive_height=True)
        title_label = MDLabel(text=workout_data['name'], font_style="H6", bold=True, adaptive_height=True)
        close_button = MDIconButton(icon="close", on_release=self.close_dialog)
        title_box.add_widget(title_label)
        title_box.add_widget(close_button)
        content.add_widget(title_box)

        content.add_widget(MDLabel(text=workout_data['description'], theme_text_color="Secondary", adaptive_height=True))
        details_text = f"Duration: {workout_data['duration']}\nDifficulty: {workout_data['difficulty']}\nDays per week: {workout_data['days_per_week']}"
        content.add_widget(MDLabel(text=details_text, theme_text_color="Secondary", adaptive_height=True))
        content.add_widget(MDLabel(text="Exercises:", bold=True, adaptive_height=True))

        for exercise in workout_data['exercises']:
            exercise_text = f"• {exercise['name']}: {exercise['sets']} sets × {exercise['reps']}"
            content.add_widget(MDLabel(text=exercise_text, adaptive_height=True))

        self.dialog = MDDialog(
            type="custom",
            content_cls=content,
            buttons=[
                MDTextButton(text="ADD TO MY WORKOUTS", on_release=lambda x: self.add_to_my_workouts(workout_data)),
                MDTextButton(text="CLOSE", on_release=self.close_dialog),
            ],
        )
        self.dialog.open()
        
    def add_to_my_workouts(self, workout_data):
        self.close_dialog()
        if workout_data not in self.my_workouts:
            self.my_workouts.append(workout_data)
            message = f" Added '{workout_data['name']}' to your workouts!"
        else:
            message = f"ℹ '{workout_data['name']}' is already in your workouts."
        
        self.dialog = MDDialog(
            title="Success",
            text=f"{message}\n\nTotal workouts: {len(self.my_workouts)}",
            buttons=[MDTextButton(text="OK", on_release=self.close_dialog)],
        )
        self.dialog.open()

    def show_add_workout_dialog(self):
        self.show_dialog("Add Workout", "Feature coming soon! You can add custom workouts in the next update.")

    # --- AI Personalization Methods ---
    def open_gender_menu(self):
        menu_items = [
            {
                "text": gender,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=gender: self.select_gender(x),
            } for gender in self.genders
        ]
        self.gender_menu = MDDropdownMenu(
            caller=self.root.ids.gender_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.gender_menu.open()

    def select_gender(self, gender):
        self.root.ids.gender_dropdown.text = gender
        self.selected_gender = gender
        if self.gender_menu:
            self.gender_menu.dismiss()

    def open_activity_menu(self):
        menu_items = [
            {
                "text": level,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=level: self.select_activity_level(x),
            } for level in self.activity_levels
        ]
        self.activity_menu = MDDropdownMenu(
            caller=self.root.ids.activity_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.activity_menu.open()

    def select_activity_level(self, level):
        self.root.ids.activity_dropdown.text = level
        self.activity_level = level
        if self.activity_menu:
            self.activity_menu.dismiss()

    def open_goal_menu(self):
        menu_items = [
            {
                "text": goal,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=goal: self.select_primary_goal(x),
            } for goal in self.fitness_goals
        ]
        self.goal_menu = MDDropdownMenu(
            caller=self.root.ids.goal_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.goal_menu.open()

    def select_primary_goal(self, goal):
        self.root.ids.goal_dropdown.text = goal
        self.primary_goal = goal
        if self.goal_menu:
            self.goal_menu.dismiss()

    def open_diet_menu(self):
        menu_items = [
            {
                "text": diet,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=diet: self.select_diet_preference(x),
            } for diet in self.diet_preferences
        ]
        self.diet_menu = MDDropdownMenu(
            caller=self.root.ids.diet_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.diet_menu.open()

    def select_diet_preference(self, diet):
        self.root.ids.diet_dropdown.text = diet
        self.diet_preference = diet
        if self.diet_menu:
            self.diet_menu.dismiss()

    def open_budget_menu(self):
        menu_items = [
            {
                "text": budget,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=budget: self.select_budget_level(x),
            } for budget in self.budget_levels
        ]
        self.budget_menu = MDDropdownMenu(
            caller=self.root.ids.budget_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.budget_menu.open()

    def select_budget_level(self, budget):
        self.root.ids.budget_dropdown.text = budget
        self.budget_level = budget
        if self.budget_menu:
            self.budget_menu.dismiss()

    def open_conditions_menu(self):
        menu_items = [
            {
                "text": condition,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=condition: self.add_condition(x),
            } for condition in self.health_conditions
        ]
        self.conditions_menu = MDDropdownMenu(
            caller=self.root.ids.conditions_chip_box,
            items=menu_items,
            width_mult=4,
        )
        self.conditions_menu.open()

    def add_condition(self, condition):
        if condition == "None":
            self.selected_conditions = ["None"]
        elif condition not in self.selected_conditions:
            if "None" in self.selected_conditions:
                self.selected_conditions.remove("None")
            self.selected_conditions.append(condition)
        self.update_conditions_chips()
        if self.conditions_menu:
            self.conditions_menu.dismiss()

    def clear_conditions(self):
        self.selected_conditions = []
        self.update_conditions_chips()

    def remove_condition(self, condition):
        if condition in self.selected_conditions:
            self.selected_conditions.remove(condition)
        self.update_conditions_chips()

    def update_conditions_chips(self):
        self.root.ids.conditions_chip_box.clear_widgets()
        
        if not self.selected_conditions:
            no_conditions_label = MDLabel(
                text="No conditions selected. Click 'Add Condition' to add.",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(30)
            )
            self.root.ids.conditions_chip_box.add_widget(no_conditions_label)
        else:
            chip_layout = MDBoxLayout(orientation='horizontal', adaptive_height=True, spacing=dp(5))
            chip_layout.size_hint_y = None
            chip_layout.height = dp(40)
            
            for condition in self.selected_conditions:
                chip = MDChip(
                    text=condition,
                    on_release=lambda x, cond=condition: self.remove_condition(cond)
                )
                chip_layout.add_widget(chip)
            
            self.root.ids.conditions_chip_box.add_widget(chip_layout)

    def validate_personalization_inputs(self):
        age = self.root.ids.age_field.text
        height = self.root.ids.height_field.text
        weight = self.root.ids.weight_field.text
        goal_weight = self.root.ids.goal_weight_field.text
        goal_time = self.root.ids.goal_time_field.text
        
        if not all([age, height, weight, goal_weight, goal_time, 
                     self.selected_gender, self.activity_level, self.primary_goal,
                     self.diet_preference, self.budget_level]):
            return False, "Please fill all fields"
        
        try:
            age = int(age)
            height = float(height)
            weight = float(weight)
            goal_weight = float(goal_weight)
            goal_time = int(goal_time)
            
            if age < 10 or age > 100:
                return False, "Please enter a valid age (10-100)"
            if height < 100 or height > 250:
                return False, "Please enter a valid height (100-250 cm)"
            if weight < 30 or weight > 300:
                return False, "Please enter a valid weight (30-300 kg)"
            if goal_time < 1 or goal_time > 104:
                return False, "Please enter a valid target time (1-104 weeks)"
                
        except ValueError:
            return False, "Please enter valid numbers"
        
        return True, "Valid"

    def generate_ai_plan(self):
        is_valid, message = self.validate_personalization_inputs()
        if not is_valid:
            self.show_error(message)
            return
        
        self.loading_dialog = MDDialog(
            title="AI Generating Your Plan...",
            text="Using Google Gemini AI to create your personalized fitness plan...",
            type="simple"
        )
        self.loading_dialog.open()
        
        user_data = {
            "age": int(self.root.ids.age_field.text),
            "gender": self.selected_gender,
            "height": float(self.root.ids.height_field.text),
            "current_weight": float(self.root.ids.weight_field.text),
            "goal_weight": float(self.root.ids.goal_weight_field.text),
            "goal_time_weeks": int(self.root.ids.goal_time_field.text),
            "activity_level": self.activity_level,
            "primary_goal": self.primary_goal,
            "diet_preference": self.diet_preference,
            "budget_level": self.budget_level,
            "health_conditions": self.selected_conditions
        }
        
        self.generate_plan_with_ai(user_data, self.loading_dialog)

    def generate_plan_with_ai(self, user_data, loading_dialog):
        def generate_thread():
            try:
                plan = self.plan_generator.generate_personalized_plan(user_data)
                self.current_plan = plan
                
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.show_generated_plan(plan, loading_dialog))
                    
            except Exception as e:
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.show_error(f"Error: {str(e)}"))
        
        from threading import Thread
        thread = Thread(target=generate_thread)
        thread.daemon = True
        thread.start()

    def show_generated_plan(self, plan, loading_dialog):
        loading_dialog.dismiss()
        self.switch_to_plan_display(plan)

    def display_ai_plan(self, plan_data):
        nutrition_text = self.clean_text(plan_data.get('nutrition_plan', 'No nutrition plan available'))
        workout_text = self.clean_text(plan_data.get('workout_plan', 'No workout plan available'))
        notes_text = self.clean_text(plan_data.get('important_notes', 'No notes available'))
        
        self.root.ids.nutrition_plan.text = nutrition_text
        self.root.ids.workout_plan.text = workout_text
        self.root.ids.important_notes.text = notes_text

    def clean_text(self, text):
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                line = line.replace('**', '')
                line = line.replace('*', '•')
                line = line.replace('-', '•')
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def save_ai_plan(self):
        if self.current_plan:
            success = self.save_user_plan(self.current_plan)
            if success:
                dialog = MDDialog(
                    title="Success",
                    text="Your AI-powered plan has been saved!",
                    buttons=[MDTextButton(text="OK", on_release=lambda x: dialog.dismiss())]
                )
            else:
                dialog = MDDialog(
                    title="Error",
                    text="Failed to save the plan.",
                    buttons=[MDTextButton(text="OK", on_release=lambda x: dialog.dismiss())]
                )
            dialog.open()

    def save_user_plan(self, plan_data):
        try:
            conn = sqlite3.connect(self.DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_plans (plan_data, created_date)
                VALUES (?, ?)
            ''', (json.dumps(plan_data), datetime.now().strftime("%Y-%m-%d %H:%M")))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error saving plan: {e}")
            return False

    def get_saved_plans(self):
        try:
            conn = sqlite3.connect(self.DB_NAME)
            cursor = conn.cursor()
            cursor.execute('SELECT plan_data FROM user_plans ORDER BY created_date DESC')
            rows = cursor.fetchall()
            conn.close()
            
            plans = []
            for row in rows:
                try:
                    plan_data = json.loads(row[0])
                    plans.append(plan_data)
                except:
                    continue
            return plans
        except:
            return []

    def display_saved_plans(self):
        saved_plans_list = self.root.ids.saved_plans_list
        saved_plans_list.clear_widgets()
        
        plans = self.get_saved_plans()
        if not plans:
            empty_label = MDLabel(
                text="No saved plans found. Create your first plan!",
                halign="center",
                theme_text_color="Secondary",
                size_hint_y=None,
                height=dp(50)
            )
            saved_plans_list.add_widget(empty_label)
        else:
            for plan in plans:
                item = PlanListItem(plan_data=plan)
                saved_plans_list.add_widget(item)

    def view_saved_plan(self, plan_data):
        self.switch_to_plan_display(plan_data)

    # --- Utility Methods ---
    def close_dialog(self, *args):
        if self.dialog:
            self.dialog.dismiss()

    def show_dialog(self, title, text):
        self.dialog = MDDialog(
            title=title,
            text=text,
            buttons=[MDTextButton(text="OK", on_release=self.close_dialog)],
        )
        self.dialog.open()

    def show_error(self, message):
        dialog = MDDialog(
            title="Error",
            text=message,
            buttons=[MDTextButton(text="OK", on_release=lambda x: dialog.dismiss())]
        )
        dialog.open()
    # --- Custom Plan Creation Methods ---
    def my_plus_function(self, *args):
        """Opens the 'Add New Training Plan' dialog."""
        if self.dialog:
            self.dialog.dismiss()

        content = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            padding="20dp",
            spacing="10dp",
        )
        
        content.dialog_selected_exercises = []  
        content.name_field = MDTextField(hint_text="New training plan name")
        content.add_widget(content.name_field)

        # Layout for the 'Add' buttons
        button_layout = MDBoxLayout(
            orientation='horizontal',
            adaptive_height=True,
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40)
        )
        content.add_widget(button_layout)

        add_exercise_button = MDRaisedButton(
            text="Add Exercise",
            size_hint_x=0.45
        )
        button_layout.add_widget(add_exercise_button)

        add_plan_button = MDRaisedButton(
            text="Add Plan",
            size_hint_x=0.45
        )
        button_layout.add_widget(add_plan_button)

        add_break_button = MDIconButton(
            icon="timer-sand",
            tooltip_text="Add 1-Min Break",
            size_hint_x=0.1,
            on_release=partial(self.add_break_to_dialog, content)
        )
        button_layout.add_widget(add_break_button)
        
        # Scrollable list for added items
        scroll_view = ScrollView(size_hint_y=None, height=dp(150))
        content.exercise_list = MDList()
        scroll_view.add_widget(content.exercise_list)
        content.add_widget(scroll_view)

        # Create the 'Add Exercise' dropdown
        all_exercises = self.get_all_exercises_as_list()
        exercise_menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": ex_name,
                "on_release": partial(self.add_exercise_to_dialog, ex_id, ex_name, content)
            }
            for ex_id, ex_name in all_exercises
        ]
        self.exercise_menu = MDDropdownMenu(
            caller=add_exercise_button,
            items=exercise_menu_items,
            width_mult=4,
        )
        add_exercise_button.on_release = self.exercise_menu.open

        # Create the 'Add Plan' dropdown
        all_plans = self.get_all_training_types_as_dict().items()
        plan_menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": plan_name,
                "on_release": partial(self.add_plan_to_dialog, plan_id, plan_name, content)
            }
            for plan_name, plan_id in all_plans
        ]
        self.plan_menu = MDDropdownMenu(
            caller=add_plan_button,
            items=plan_menu_items,
            width_mult=4,
        )
        add_plan_button.on_release = self.plan_menu.open

        # Create the final dialog
        self.dialog = MDDialog(
            title="Add New Training Plan",
            type="custom",
            content_cls=content,
            buttons=[
                MDTextButton(text="CANCEL", on_release=self.close_dialog),
                MDRaisedButton(text="SAVE", on_release=lambda x: self.save_new_item(content)),
            ],
        )
        self.dialog.open()

    def save_new_item(self, content, *args):
        """Saves the new custom training plan to the database."""
        
        new_name = content.name_field.text.strip()
        
        if not new_name:
            toast("Name cannot be empty")
            return

        # Uniqueness Check
        try:
            query = "SELECT COUNT(*) FROM training_types WHERE name = ?"
            records = self.db_fetch(query, (new_name,))
            count = records[0][0] if records else 0

            if count > 0:
                toast(f"Error: The name '{new_name}' already exists.")
                return
        
        except Exception as e:
            print(f"Database error checking name: {e}")
            toast("Error checking database. Please try again.")
        selected_ids = [item.save_id for item in content.dialog_selected_exercises]
        
        if not selected_ids:
            toast("Please add at least one exercise or plan")
        exercise_ids_str = ",".join(selected_ids)

        # Save the new training plan to the database
        try:
            query = "INSERT INTO training_types (name, exercise_ids) VALUES (?, ?)"
            self.db_execute(query, (new_name, exercise_ids_str))
            
            # Refresh the main dropdown menu
            self.refresh_training_plan_dropdown()
            
            toast(f"Plan '{new_name}' saved!")
            self.close_dialog()

        except Exception as e:
            print(f"Database error saving plan: {e}")
            toast("Error saving to database.")

    def get_all_exercises_as_list(self):
        """Fetches all exercises from the DB as a list of (id, name) tuples."""
        try:
            query = "SELECT unique_id, name FROM exercise_type ORDER BY name"
            records = self.db_fetch(query)
            return records
        except Exception as e:
            print(f"Error fetching all exercises: {e}")
            return []

    def add_exercise_to_dialog(self, ex_id, ex_name, content, *args):
        """Adds a selected exercise to the dialog's visual list."""
            
        item = OneLineAvatarIconListItem(
            text=ex_name
        )
        item.ex_id = ex_id
        item.ex_name = ex_name
        item.save_id = str(ex_id)
        
        content.dialog_selected_exercises.append(item)
        
        left_icon = IconLeftWidget(
            icon="dumbbell"
        )
        item.add_widget(left_icon)

        delete_icon = IconRightWidget(
            icon="trash-can-outline"
        )
        delete_icon.on_release = partial(self.remove_exercise_from_dialog, item, content)
        
        item.add_widget(delete_icon)
        content.exercise_list.add_widget(item)
        
        self.exercise_menu.dismiss()

    def remove_exercise_from_dialog(self, item_widget, content, *args):
        """Called when a delete icon is clicked to remove the item."""
        content.dialog_selected_exercises.remove(item_widget)
        content.exercise_list.remove_widget(item_widget)

    def refresh_training_plan_dropdown(self):
        """Re-builds the main 'Training' dropdown to show new plans."""
        training_plans_dict = self.get_all_training_types_as_dict()
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": name,
                "on_release": lambda x=name, y=uid: self.menu_callback((x, y)),
            }
            for name, uid in training_plans_dict.items()
        ]
        self.menu = MDDropdownMenu(
            caller=self.root.ids.dropdown_item,  
            items=menu_items,  
            width_mult=5
        )
        self.root.ids.dropdown_item.set_item("Select")
        self.selected_training_id = None

    def add_break_to_dialog(self, content, *args):
        """Adds a 1-minute break to the dialog's visual list."""
        ex_id, ex_name = -1,
        
        item = OneLineAvatarIconListItem(
            text=ex_name
        )
        item.ex_id = ex_id
        item.ex_name = ex_name
        item.save_id = str(ex_id)

        content.dialog_selected_exercises.append(item)
        
        left_icon = IconLeftWidget(
            icon="timer-sand"
        )
        item.add_widget(left_icon)

        delete_icon = IconRightWidget(
            icon="trash-can-outline"
        )
        delete_icon.on_release = partial(self.remove_exercise_from_dialog, item, content)
        
        item.add_widget(delete_icon)
        content.exercise_list.add_widget(item)

    def confirm_delete_plan(self, *args):
        """Checks if a plan is selected, then opens a confirmation dialog."""
        if self.selected_training_id is None:
            toast("Please select a training plan from the dropdown to delete.")
            return

        plan_name = self.root.ids.dropdown_item.text
        
        if self.dialog:
            self.dialog.dismiss()
            
        self.dialog = MDDialog(
            title="Delete Plan?",
            text=f"Are you sure you want to permanently delete the plan: [b]{plan_name}[/b]?",
            buttons=[
                MDTextButton(text="CANCEL", on_release=self.close_dialog),
                MDRaisedButton(
                    text="DELETE",
                    md_bg_color=self.theme_cls.error_color,
                    on_release=self.execute_delete_plan
                ),
            ],
        )
        self.dialog.open()

    def execute_delete_plan(self, *args):
        """Deletes the plan from the database and refreshes the UI."""
        plan_id_to_delete = self.selected_training_id
        plan_name = self.root.ids.dropdown_item.text
        
        try:
            query = "DELETE FROM training_types WHERE unique_id = ?"
            self.db_execute(query, (plan_id_to_delete,))
            
            toast(f"Plan '{plan_name}' has been deleted.")
            
            self.refresh_training_plan_dropdown()
            self.close_dialog()
        
        except Exception as e:
            print(f"Database error deleting plan: {e}")
            toast("An error occurred while deleting the plan.")
            self.close_dialog()

    def add_plan_to_dialog(self, plan_id, plan_name, content, *args):
        """Adds a selected plan to the dialog's visual list."""
        item = OneLineAvatarIconListItem(
            text=f"PLAN: {plan_name}"
        )
        
        item.save_id = f"P{plan_id}"
        
        left_icon = IconLeftWidget(
            icon="clipboard-list-outline"
        )
        item.add_widget(left_icon)
        
        delete_icon = IconRightWidget(
            icon="trash-can-outline"
        )
        delete_icon.on_release = partial(self.remove_exercise_from_dialog, item, content)
        
        item.add_widget(delete_icon)
        
        content.dialog_selected_exercises.append(item)
        content.exercise_list.add_widget(item)
        
        self.plan_menu.dismiss()

    def build_user_menu(self):
        """Creates the dropdown menu for switching users."""
        users = self.db_fetch("SELECT user_id, name FROM users ORDER BY name")
        
        menu_items = []
        for user_id, name in users:
            menu_items.append({
                "viewclass": "OneLineListItem",
                "text": name,
                "on_release": partial(self.switch_user, user_id, name)
            })

        menu_items.append({
            "viewclass": "OneLineListItem",
            "text": "[+] Add New User",
            "on_release": self.show_add_user_dialog
        })
        
        menu_items.append({
            "viewclass": "OneLineListItem",
            "text": "Delete Current User",
            "on_release": self.confirm_delete_user,
            "_txt_color": self.theme_cls.error_color
        })

        self.user_menu = MDDropdownMenu(
            caller=self.user_dropdown,
            items=menu_items,
            width_mult=4
        )

    def open_user_menu(self):
        self.user_menu.open()

    def load_user_data(self):
        """A new function to load all data for the current self.user_id"""
        self.workout_dates = self.get_workout_dates(self.user_id)
        self.weight_data = self.get_all_weight_data()
        self.populate_calendar()
        self.show_weekly_progress("Calories Burned")
        
    def switch_user(self, user_id, name, *args):
        """Switches the active user and reloads all UI data."""
        self.user_id = user_id
        self.user_dropdown.set_item(name)
        self.user_menu.dismiss()
        toast(f"Switched to user: {name}")
        self.load_user_data()

    def show_add_user_dialog(self, *args):
        """Shows a dialog to add a new user."""
        self.user_menu.dismiss()
        if self.dialog:
            self.dialog.dismiss()
        
        content = MDBoxLayout(
            orientation='vertical',
            size_hint_y=None,
            adaptive_height=True,
            padding="20dp",
            spacing="10dp"
        )
        
        name_field = MDTextField(hint_text="New user's name")
        content.add_widget(name_field)
        
        self.dialog = MDDialog(
            title="Add New User",
            type="custom",
            content_cls=content,
            buttons=[
                MDTextButton(text="CANCEL", on_release=self.close_dialog),
                MDRaisedButton(text="SAVE", on_release=lambda x: self.save_new_user(name_field.text))
            ]
        )
        self.dialog.open()

    def save_new_user(self, name):
        """Saves the new user to the database."""
        if not name.strip():
            toast("Name cannot be empty")
            return
            
        try:
            self.db_execute("INSERT INTO users (name) VALUES (?)", (name,))
            toast(f"User '{name}' added!")
            self.close_dialog()
            self.build_user_menu() 
        except Exception as e:
            toast(f"Error: {e}")

    def confirm_delete_user(self, *args):
        """Shows a confirmation dialog before deleting a user."""
        self.user_menu.dismiss()
        
        # --- SAFETY CHECK ---
        # We must not allow deletion of the main/default user (ID 1)
        if self.user_id == 1:
            toast("Cannot delete the default user.")
            return

        user_name = self.user_dropdown.text
        
        if self.dialog:
            self.dialog.dismiss()
            
        self.dialog = MDDialog(
            title="Delete User?",
            text=f"This will permanently delete [b]{user_name}[/b] and all their associated data (workouts, weights, streaks).\n\nThis action cannot be undone.",
            buttons=[
                MDTextButton(text="CANCEL", on_release=self.close_dialog),
                MDRaisedButton(
                    text="DELETE",
                    md_bg_color=self.theme_cls.error_color,
                    on_release=self.execute_delete_user
                ),
            ],
        )
        self.dialog.open()

    def execute_delete_user(self, *args):
        """
        Deletes the current user and all their data from the database.
        """
        user_id_to_delete = self.user_id
        user_name = self.user_dropdown.text
        
        if user_id_to_delete == 1:
            # Final safety check
            toast("Cannot delete the default user.")
            self.close_dialog()
            return            
        try:
            self.db_execute("DELETE FROM workouts WHERE user_id = ?", (user_id_to_delete,))
            self.db_execute("DELETE FROM weights WHERE user_id = ?", (user_id_to_delete,))
            self.db_execute("DELETE FROM streaks WHERE user_id = ?", (user_id_to_delete,))
            
            # Now delete the user
            self.db_execute("DELETE FROM users WHERE user_id = ?", (user_id_to_delete,))
            
            self.close_dialog()
            toast(f"User '{user_name}' has been deleted.")
            self.build_user_menu()
            
            # Switch back to the default user (ID 1)
            self.switch_user(1, "Default User")
            
        except Exception as e:
            print(f"Error deleting user: {e}")
            toast("An error occurred while deleting the user.")
            self.close_dialog()

if __name__ == '__main__':
    ComprehensiveFitnessApp().run()