import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from ui.test_tab import TestTab
from ui.settings_tab import SettingsTab
from ui.manual_tab import ManualTab
from ui.motors_tab import MotorsTab


class App:
    def __init__(self,
                 pulse_max, pulse_min, update_pulse_value):
        self.root = ThemedTk()
        self.root.get_themes()
        self.root.set_theme("arc")
        self.root.title("Тестирование")

        # Создаем вкладки
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill=tk.BOTH)

        # Вкладки
        self.test_tab = TestTab(self.notebook)
        self.settings_tab = SettingsTab(self.notebook)
        self.manual_tab = ManualTab(self.notebook)
        self.motors_tab = MotorsTab(self.notebook)

        self.notebook.bind("<<NotebookTabChanged>>", self.update_frame)

        self.root.protocol("WM_DELETE_WINDOW", self.close_application)
        self.root.bind('<Escape>', self.emergency_stop)

    def update_frame(self, event):
        pass  # Реализовать, если нужно

    def emergency_stop(self, event=None):
        print("Экстренная остановка")

    def close_application(self):
        print("Закрытие приложения")
        self.root.destroy()

    def run(self):
        self.root.mainloop()