import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from PIL import Image, ImageTk


class TestTab:
    def __init__(self, notebook, pulse_max=2200, pulse_min=800, update_pulse_values=None):
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Тест")

        self.pulse_max = pulse_max
        self.pulse_min = pulse_min
        self.update_pulse_values = update_pulse_values

        self.create_input_fields()
        self.create_image_logo()
        self.create_pwm_controls()
        self.create_progress_bar()
        self.create_com_port_controls()
        self.create_buttons()

    def create_input_fields(self):
        input_frame = tk.Frame(self.frame)
        input_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky='ew')

        tk.Label(input_frame, text="Название двигателя:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tk.Entry(input_frame).grid(row=0, column=1, padx=10, pady=5, sticky='ew')

        tk.Label(input_frame, text="Название пропеллера:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
        tk.Entry(input_frame).grid(row=1, column=1, padx=10, pady=5, sticky='ew')

    def create_image_logo(self):
        try:
            image = Image.open("dron_motors.png")
            image = image.resize((250, 100), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(image)
            tk.Label(self.frame, image=logo_photo).grid(row=0, column=2, rowspan=2, padx=10, pady=5, sticky='n')
        except FileNotFoundError:
            print("Изображение 'dron_motors.png' не найдено.")

    def create_pwm_controls(self):
        """Создает ползунки для управления ШИМ (PWM)"""
        speed_max_percent_label = tk.Label(self.frame, text="Максимальное значение ШИМ:")
        speed_max_percent_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')

        self.speed_max_percent_slider = tk.Scale(
            self.frame,
            from_=800,  # Начальное значение
            to=2200,  # Максимальное значение
            orient=tk.HORIZONTAL,
            length=300,
            resolution=100,  # Шаг изменения
            tickinterval=150,  # Интервал для отметок
            command=lambda _: self.update_pulse_values() if self.update_pulse_values else None
        )
        self.speed_max_percent_slider.set(self.pulse_max)
        self.speed_max_percent_slider.grid(row=2, column=1, padx=10, pady=5, sticky='ew')

        speed_min_percent_label = tk.Label(self.frame, text="Минимальное значение ШИМ:")
        speed_min_percent_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')

        self.speed_min_percent_slider = tk.Scale(
            self.frame,
            from_=800,  # Начальное значение
            to=2200,  # Максимальное значение
            orient=tk.HORIZONTAL,
            length=300,
            resolution=100,  # Шаг изменения
            tickinterval=150,  # Интервал для отметок
            command=lambda _: self.update_pulse_values() if self.update_pulse_values else None
        )
        self.speed_min_percent_slider.set(self.pulse_min)
        self.speed_min_percent_slider.grid(row=3, column=1, padx=10, pady=5, sticky='ew')

    def create_progress_bar(self):
        pass  # Вынести логику прогресс бара

    def create_com_port_controls(self):
        pass  # Вынести логику COM-порта

    def create_buttons(self):
        pass  # Вынести логику кнопок