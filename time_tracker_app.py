import customtkinter as ctk
import pandas as pd
import datetime
import os
import sys
import subprocess
import tempfile
import tkinter
from tkinter import messagebox
import psutil

my_app_id = 'RyanSims.TimeTracker' 
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
except (ImportError, AttributeError):
    # This will fail on non-Windows systems, which is fine
    pass


# Configuration
LOG_FILE = "time_log.csv"
REPORT_FILE = "time_report.txt"
ICON_FILE = "icon.ico"
LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), "time_tracker.lock")
MAX_RECENT_PROJECTS = 15

# Main Application Class
class TimeTrackerApp(ctk.CTk):
    def __init__(self, lock_file_handle):
        super().__init__()
        
        self.lock_file_handle = lock_file_handle

        # Window setup
        self.title("Time Tracker")
        ctk.set_appearance_mode("dark")
        self.attributes('-topmost', True)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Class attributes
        self.running_project_code = None
        self.start_time = None
        self.recent_projects = self.load_recent_projects()
        
        self.create_widgets()
        self.ensure_log_file_exists()
        self.resize_to_fit_content()
        
        try:
            if os.path.exists(ICON_FILE):
                self.iconbitmap(ICON_FILE)
        except Exception as e:
            print(f"Error setting main window icon: {e}")
            
        self.after(100, lambda: self.project_entry.focus())

    def on_closing(self):
        # Handles the window close event
        if self.running_project_code:
            print("App closed with active timer. Saving entry...")
            self.stop_timer(is_closing=True)
        
        try:
            self.lock_file_handle.close()
            os.remove(LOCK_FILE_PATH)
        except Exception as e:
            print(f"Could not remove lock file: {e}")
            
        self.destroy()

    def create_widgets(self):
        """Creates and places all the GUI elements in the window."""
        self.stopped_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.running_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.report_button = ctk.CTkButton(self.stopped_frame, text="Generate Report", command=self.generate_report)
        self.report_button.pack(fill="x", padx=15, pady=(15, 5))
        self.edit_file_button = ctk.CTkButton(self.stopped_frame, text="Edit Log File", command=self.edit_log_file)
        self.edit_file_button.pack(fill="x", padx=15, pady=5)
        
        self.input_frame = ctk.CTkFrame(self.stopped_frame)
        self.input_frame.pack(fill="x", padx=15, pady=15, ipady=10)
        ctk.CTkLabel(self.input_frame, text="Enter or Select Project:", font=("Arial", 12)).pack(pady=(5,0))
        self.project_entry = ctk.CTkComboBox(self.input_frame, width=200, values=self.recent_projects)
        self.project_entry.set("")
        self.project_entry.pack(pady=10, padx=10)
        
        self.project_entry.bind("<Return>", self.start_timer_on_enter)
        
        self.start_button = ctk.CTkButton(self.input_frame, text="Start Timer", command=self.start_timer, fg_color="#43A047", hover_color="#2E7D32")
        self.start_button.pack(pady=5, padx=10)

        self.running_project_label = ctk.CTkLabel(self.running_frame, text="", font=("Arial", 16, "bold"))
        self.running_project_label.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        self.stop_button = ctk.CTkButton(self.running_frame, text="Stop Timer", command=self.stop_timer, fg_color="#D32F2F", hover_color="#B71C1C")
        self.stop_button.pack(side="right", padx=15, pady=15)

        self.stopped_frame.pack(fill="both", expand=True)

    # Actively resize the window
    def resize_to_fit_content(self):
        """Calculates required size and actively resizes the window to fit."""
        self.update_idletasks() # Ensure widget sizes are calculated
        
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        
        # Set the window's geometry to the calculated required size
        self.geometry(f"{width}x{height}")
        # Also set this as the minimum size to prevent manual shrinking
        self.minsize(width, height)

    def start_timer_on_enter(self, event):
        """Callback function for the Enter key press event."""
        self.start_timer()

    def start_timer(self):
        project_code = self.project_entry.get().strip()
        if not project_code: return
        self.running_project_code = project_code
        self.start_time = datetime.datetime.now()
        self.stopped_frame.pack_forget()
        self.running_project_label.configure(text=f"Running: {self.running_project_code}")
        self.running_frame.pack(fill="both", expand=True)
        self.resize_to_fit_content()

    def stop_timer(self, is_closing=False):
        if not self.running_project_code: return
        end_time = datetime.datetime.now()
        duration = end_time - self.start_time
        log_entry = { "project_code": [self.running_project_code], "start_time": [self.start_time.strftime("%Y-%m-%d %H:%M:%S")], "end_time": [end_time.strftime("%Y-%m-%d %H:%M:%S")], "duration_seconds": [duration.total_seconds()] }
        df = pd.DataFrame(log_entry)
        df.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)
        self.running_project_code = None
        self.start_time = None
        
        if not is_closing:
            self.project_entry.set("")
            self.recent_projects = self.load_recent_projects()
            self.project_entry.configure(values=self.recent_projects)
            self.running_frame.pack_forget()
            self.stopped_frame.pack(fill="both", expand=True)
            self.resize_to_fit_content()
            self.project_entry.focus()
    
    def load_recent_projects(self):
        try:
            if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0: return []
            df = pd.read_csv(LOG_FILE)
            if df.empty: return []
            df['start_time'] = pd.to_datetime(df['start_time'])
            return df.sort_values(by='start_time', ascending=False)\
                     .drop_duplicates(subset=['project_code'], keep='first')\
                     ['project_code'].head(MAX_RECENT_PROJECTS).tolist()
        except Exception as e:
            print(f"Error loading recent projects: {e}")
            return []

    def generate_report(self):
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            messagebox.showinfo("Report", "Log file is empty.")
            return
        df = pd.read_csv(LOG_FILE)
        if df.empty:
            messagebox.showinfo("Report", "Log file is empty.")
            return
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['date'] = df['start_time'].dt.date
        grouped_data = df.groupby(['date', 'project_code'])['duration_seconds'].sum()
        with open(REPORT_FILE, "w") as f:
            f.write("--- Time Tracking Report ---\n")
            f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            for date, daily_data in grouped_data.groupby(level=0):
                f.write("\n" + "="*30 + "\n")
                f.write(f"DATE: {date.strftime('%Y-%m-%d')}\n")
                f.write("="*30 + "\n")
                for (d, project_code), seconds in daily_data.items():
                    hours, rem = divmod(seconds, 3600)
                    minutes, seconds = divmod(rem, 60)
                    f.write(f"  Project: {project_code}\n")
                    f.write(f"    Total Time: {int(hours):02}:{int(minutes):02}:{int(seconds):02}\n\n")
        print(f"Report generated: {REPORT_FILE}")
        self.open_file(REPORT_FILE)

    def edit_log_file(self):
        if os.path.exists(LOG_FILE): self.open_file(LOG_FILE)
        else: print("Log file does not exist yet.")

    def ensure_log_file_exists(self):
        if not os.path.exists(LOG_FILE):
            pd.DataFrame(columns=["project_code", "start_time", "end_time", "duration_seconds"]).to_csv(LOG_FILE, index=False)
            print(f"Log file created: {LOG_FILE}")
    
    def open_file(self, filepath):
        try:
            # Account for different operating systems
            if sys.platform == "win32": os.startfile(filepath)
            elif sys.platform == "darwin": subprocess.run(["open", filepath], check=True)
            else: subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e: print(f"Error opening file: {e}")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")

    if os.path.exists(LOCK_FILE_PATH):
        # The lock file exists, so check if the process is still running
        try:
            with open(LOCK_FILE_PATH, 'r') as f:
                old_pid = int(f.read())
            
            # Check if a process with the old PID is still running
            if psutil.pid_exists(old_pid):
                messagebox.showerror(
                    "Application Already Running",
                    "Another instance of Time Tracker is already running."
                )
                sys.exit(1)
            else:
                # The process is not running, so the lock file is stale.
                print("Found a stale lock file. The application will start.")
        except (IOError, ValueError):
            # The lock file is corrupt or empty.
            print("Found a corrupt lock file. The application will start.")
    
    try:
        lock_file = open(LOCK_FILE_PATH, 'w')
        lock_file.write(str(os.getpid()))
        lock_file.flush() # Ensure the PID is written to disk immediately
        
        app = TimeTrackerApp(lock_file_handle=lock_file)
        app.mainloop()
    
    except Exception as e:
        messagebox.showerror("Application Error", f"An unexpected error occurred during startup: {e}")
        sys.exit(1)