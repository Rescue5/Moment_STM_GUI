import serial
import serial.tools.list_ports
import time
import threading
import queue
from tkinter import messagebox
import csv
import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk
from tkinter import scrolledtext
from PIL import Image, ImageTk
import os
import datetime
import subprocess
import platform
from dm_cli import DMCLIHandler

dm_cli_handler = None

last_command = None

stop_event = threading.Event()
command_queue = queue.Queue()
lock = threading.Lock()
test_running = threading.Event()

count = 0
previous_rpm = []
current_rpm = []
current_speed = None
current_speed_check = 0
previous_speed = None  # Предыдущая скорость для анализа
stand_name = None  # Название стенда

rpm_received = False

# Добавляем в раздел глобальных переменных
previous_avg_rpm = None  # Среднее RPM предыдущей скорости
current_avg_rpm = None  # Среднее RPM текущей скорости
rpm_count = 0  # Счетчик RPM для текущей скорости

# Добавляем переменные для прогресс-бара
test_target_speed = None  # Целевая скорость для текущего теста
progress_complete = False  # Флаг завершения прогресса

# Настройки
BAUD_RATE = 115200

ser = None  # Глобальная переменная для хранения объекта Serial
process_commands_thread = None  # Поток обработки команд
read_serial_thread = None  # Поток чтения данных

# Переменные для логирования
log_file = None
csv_file = None
log_file_lock = threading.Lock()


def parse_and_save_to_csv(data):
    """Парсинг строки и запись в CSV + анализ оборотов."""
    global current_rpm, previous_rpm, current_speed, previous_speed
    global current_avg_rpm, previous_avg_rpm, rpm_count
    global test_target_speed, progress_complete
    global rpm_received, current_speed_check

    if data.startswith("Speed set to:"):
        parts = data.split(":")
        try:
            speed = int(parts[1].strip())
            current_speed_check = speed
            update_progress_bar(speed)
        except (IndexError, ValueError) as e:
            log_to_console(f"Ошибка парсинга скорости: {data} | Ошибка: {e}")
            return

    elif data.startswith("Скорость:"):
        parts = data.split(":")
        try:
            speed = int(parts[1].strip())
            moment = None
            thrust = None
            rpm = None
            current = None
            voltage = None
            power = None

            if stand_name == "пропеллер":
                if len(parts) >= 8:
                    moment = float(parts[3].strip())
                    thrust = float(parts[5].strip())
                    rpm = float(parts[7].strip())
                    current = float(parts[9].strip())
                    voltage = float(parts[11].strip())
                    power = float(parts[13].strip())
                else:
                    log_to_console(
                        "Недостаточно данных для пропеллера: " + data)
                    return
            elif stand_name == "момент":
                if len(parts) >= 8:
                    moment = float(parts[3].strip())
                    thrust = float(parts[5].strip())
                    rpm = float(parts[7].strip())
                    current = float(parts[9].strip())
                    voltage = float(parts[11].strip())
                    power = float(parts[13].strip())
                else:
                    log_to_console("Недостаточно данных для момента: " + data)
                    return
            elif stand_name == "шпиндель":
                if len(parts) >= 8:
                    moment = float(parts[3].strip())
                    thrust = float(parts[5].strip())
                    rpm = float(parts[7].strip())
                    current = float(parts[9].strip())
                    voltage = float(parts[11].strip())
                    power = float(parts[13].strip())
                else:
                    log_to_console("Недостаточно данных для шпинделя: " + data)
            else:
                log_to_console("Неизвестный тип стенда.")
                return

            # Проверяем, существует ли файл CSV
            write_headers = False
            if test_running.is_set() and csv_file:
                if not os.path.exists(csv_file):
                    write_headers = True
                else:
                    # Если файл существует, проверяем его размер
                    if os.path.getsize(csv_file) == 0:
                        write_headers = True

                with log_file_lock:
                    with open(csv_file, 'a', newline='') as csvfile:
                        csv_writer = csv.writer(csvfile, delimiter=';')
                        if write_headers:
                            csv_writer.writerow(
                                ["Speed", "Moment", "Thrust", "RPM", "Current", "Voltage", "Power"])
                        csv_writer.writerow([speed, moment, thrust, rpm, current, voltage, power])

            # Анализ RPM
            if current_speed != speed:
                if current_avg_rpm is not None:
                    previous_avg_rpm = current_avg_rpm  # Обновляем предыдущую среднюю скорость

                # Сбрасываем данные для новой скорости
                previous_speed = current_speed
                current_speed = speed
                current_rpm = []
                rpm_count = 0
                current_avg_rpm = None

            # Добавляем данные RPM для текущей скорости
            if rpm is not None:
                rpm_received = True  # Получены данные по RPM
                current_rpm.append(rpm)
                rpm_count += 1

            # Рассчитываем среднее RPM после сбора 5 значений
            if rpm_count == 5:
                current_avg_rpm = sum(current_rpm) / len(current_rpm)
                log_to_console(f"Среднее RPM для скорости {current_speed}: {current_avg_rpm:.2f}")
                if previous_avg_rpm is not None:
                    analyze_rpm()

        except (IndexError, ValueError) as e:
            log_to_console(f"Ошибка парсинга данных: {data} | Ошибка: {e}")


def analyze_rpm():
    """Анализирует средние RPM для текущей и предыдущей скорости."""
    global previous_avg_rpm, current_avg_rpm

    if previous_avg_rpm is None or current_avg_rpm is None:
        return  # Недостаточно данных для анализа

    log_to_console(f"Сравнение RPM между скоростью {previous_speed} ({previous_avg_rpm:.2f}) "
                   f"и скоростью {current_speed} ({current_avg_rpm:.2f})")

    if current_avg_rpm < previous_avg_rpm:
        log_to_console(
            "Среднее RPM на текущей скорости меньше, чем на предыдущей. Остановка теста.")
        command_queue.put("STOP")
        return

    # Вычисляем процент изменения между RPM
    rpm_change_percent = abs((current_avg_rpm - previous_avg_rpm) / (previous_avg_rpm + 1.0)) * 100

    log_to_console(f"Изменение RPM: {rpm_change_percent:.2f}%")

    # Если изменение менее 4%, останавливаем тест
    if rpm_change_percent < 4:
        log_to_console("Слишком малый рост оборотов. Остановка теста.")
        stop_test()


def connect_to_stand():
    """Выполняет команду для подключения к стенду через dm-cli и обрабатывает наименование стенда."""
    global ser, process_commands_thread, read_serial_thread, log_file, csv_file
    global stand_name
    port = com_port_combobox.get()  # Получаем выбранный порт
    script = "test_conn.lua"  # Указываем скрипт подключения

    if not port:
        log_to_console("Выберите порт из выпадающего списка.")
        return

    # Определяем базовую команду
    command = ["dm-cli", "test", "--port", port, script]

    # Если мы не на Windows, добавляем "./" для вызова исполняемого файла
    if platform.system() != "Windows":
        command[0] = f"./{command[0]}"
    try:
        if read_serial_thread is None or not read_serial_thread.is_alive():
            read_serial_thread = threading.Thread(
                target=read_serial, daemon=True)
            read_serial_thread.start()
            log_to_console("Поток чтения данных запущен.")

        if process_commands_thread is None or not process_commands_thread.is_alive():
            process_commands_thread = threading.Thread(
                target=process_commands, daemon=True)
            process_commands_thread.start()
            log_to_console("Поток обработки команд запущен.")
        # Запускаем команду и получаем вывод
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            log_to_console(f"Подключение к стенду успешно:\n{result.stdout}")

            # Ищем наименование стенда в выводе
            for line in result.stdout.splitlines():
                if "Наименование стенда:" in line:
                    stand_name = line.split(":")[1].strip().lower()
                    update_stand_name(stand_name)  # Вызываем функцию обновления интерфейса
                    log_to_console(f"Название стенда: {stand_name}")

                    # Проверяем тип стенда
                    if stand_name in ["момент", "тяга", "шпиндель"]:
                        instruction_label.config(
                            text=f"Стенд: {stand_name.capitalize()}. Теперь можно запускать тест."
                        )
                        start_button.config(state=tk.NORMAL)  # Активируем кнопку "Запустить тест"
                    else:
                        log_to_console("Неизвестный тип стенда.")
                    break
            else:
                log_to_console("Не удалось определить наименование стенда.")

        else:
            log_to_console(f"Ошибка подключения:\n{result.stderr}")
    except Exception as e:
        log_to_console(f"Ошибка выполнения dm-cli: {e}")


def log_to_console(message):
    """Вывод сообщения в консольное окно и в stdout для отладки с временной меткой."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console_output.config(state=tk.NORMAL)
    console_output.insert(tk.END, f"[{timestamp}] {message}\n")
    console_output.yview(tk.END)
    console_output.config(state=tk.DISABLED)
    # Также выводим в стандартный вывод для отладки
    print(f"[{timestamp}] {message}")


def read_serial():
    """Читает данные из dm-cli и обрабатывает их в реальном времени."""
    global log_file, csv_file, stand_name, current_speed, current_speed_check, rpm_received, previous_speed

    while not stop_event.is_set():
        if dm_cli_handler and dm_cli_handler.active_process:
            try:
                line = dm_cli_handler.active_process.stdout.readline()
                if not line:
                    break
                data = line.strip()  # Убираем лишние пробелы
                log_to_console(data)  # Выводим данные в консоль

                # Записываем в лог-файл, если тест запущен
                if test_running.is_set() and log_file and csv_file:
                    with log_file_lock:
                        try:
                            with open(log_file, 'a') as lf:
                                lf.write(data + '\n')
                        except Exception as e:
                            log_to_console(f"Ошибка записи в лог-файл: {e}")

                # Анализируем RPM, если начинается строка с "Скорость:"
                if data.startswith("Скорость:") or data.startswith("Speed set to:"):
                    parse_and_save_to_csv(data)

                # Проверяем, завершен ли тест
                if "Motor stopped" in data or "Test complete" in data:
                    log_to_console("Тест завершен или двигатель остановлен.")
                    previous_rpm.clear()
                    current_rpm.clear()
                    current_speed = None
                    current_speed_check = 0
                    rpm_received = False
                    previous_speed = None
                    test_running.clear()
                    reset_test_state()
                    reset_progress_bar()

                # Проверяем название стенда
                if data.startswith("Наименование стенда:"):
                    try:
                        stand_name = data.split(":")[1].strip().lower()
                        update_stand_name(stand_name)
                        log_to_console(f"Название стенда: {stand_name}")
                        if stand_name in ["пропеллер", "момент", "шпиндель"]:
                            instruction_label.config(
                                text=f"Стенд: {stand_name.capitalize()}. Теперь можно запускать тест."
                            )
                            start_button.config(state=tk.NORMAL)
                        else:
                            log_to_console("Неизвестный тип стенда.")
                    except IndexError:
                        log_to_console("Не удалось извлечь название стенда.")
            except Exception as e:
                continue
                # log_to_console(f"Ошибка чтения данных из dm-cli: {e}")
        else:
            time.sleep(1)  # Ждем процесса dm-cli


def process_commands():
    """Функция для обработки команд от пользователя."""
    global last_command  # Используем глобальную переменную
    while not stop_event.is_set():
        try:
            command = command_queue.get(timeout=1)
        except queue.Empty:
            continue


def start_test():
    """Запуск теста."""
    global log_file, csv_file, stand_name, previous_rpm, current_rpm, current_speed, previous_speed, \
        previous_avg_rpm, current_avg_rpm, rpm_count, test_target_speed, progress_complete, dm_cli_handler
    global dm_cli_handler, read_serial_thread, process_commands_thread

    reset_test_state()
    # Сбрасываем состояния
    stop_event.clear()
    test_running.clear()

    # Создаем новый экземпляр dm_cli_handler
    dm_cli_handler = DMCLIHandler(log_to_console)

    # Перезапускаем поток чтения данных
    if read_serial_thread is None or not read_serial_thread.is_alive():
        read_serial_thread = threading.Thread(target=read_serial, daemon=True)
        read_serial_thread.start()

    # Перезапускаем поток обработки команд
    if process_commands_thread is None or not process_commands_thread.is_alive():
        process_commands_thread = threading.Thread(target=process_commands, daemon=True)
        process_commands_thread.start()

    # Получаем названия двигателя и пропеллера
    propeller_name = propeller_name_entry.get()
    if stand_name != 'шпиндель':
        engine_name = engine_name_entry.get()
    else:
        engine_name = 'shpindel'

    # Получаем значение процентов с ползунка
    percent = speed_percent_slider.get()
    pulse_max = 1000 + (percent * 10)  # Рассчитываем значение pulseMax

    if not engine_name or not propeller_name:
        log_to_console("Введите названия двигателя и пропеллера.")
        return

    # Составляем имена файлов для логов и CSV
    log_file = f"{engine_name}_{propeller_name}_log.txt"
    csv_file = f"{engine_name}_{propeller_name}_data.csv"

    # Проверяем, существуют ли уже файлы с таким именем
    if os.path.exists(log_file) or os.path.exists(csv_file):
        # Показываем предупреждение о перезаписи
        answer = messagebox.askyesno(
            "Файлы существуют",
            "Файл логов или CSV с таким именем уже существует.\nВы хотите перезаписать их?"
        )
        if not answer:
            log_to_console("Тест не запущен. Файлы уже существуют.")
            return
        else:
            try:
                if os.path.exists(log_file):
                    os.remove(log_file)
                    log_to_console(
                        f"Существующий лог-файл '{log_file}' удален.")
                if os.path.exists(csv_file):
                    os.remove(csv_file)
                    log_to_console(
                        f"Существующий CSV-файл '{csv_file}' удален.")
            except Exception as e:
                log_to_console(f"Ошибка при удалении существующих файлов: {e}")
                return

    test_target_speed = pulse_max
    log_to_console(f"Целевая скорость установлена на {test_target_speed} RPM.")

    reset_progress_bar()

    port = com_port_combobox.get()
    if not port:
        log_to_console("Выберите порт для подключения.")
        return

    dm_cli_handler = DMCLIHandler(log_to_console)

    # Запускаем dm-cli в отдельном потоке
    test_thread = threading.Thread(
        target=dm_cli_handler.run_test, args=(port, pulse_max, "moment_test.lua"), daemon=True
    )
    test_thread.start()

    # Устанавливаем флаг теста
    test_running.set()
    log_to_console("Запуск теста завершен.")


def stop_test():
    """Остановка теста или охлаждения."""
    global dm_cli_handler, test_running, read_serial_thread, process_commands_thread

    if test_running.is_set():
        log_to_console("Остановка активного процесса...")

        # Завершаем процесс dm-cli
        if dm_cli_handler and dm_cli_handler.active_process:
            dm_cli_handler.stop_command()

        # Сбрасываем флаги и останавливаем потоки
        stop_event.set()
        test_running.clear()

        # Принудительно завершаем потоки
        if read_serial_thread and read_serial_thread.is_alive():
            read_serial_thread.join(timeout=1)
            read_serial_thread = None

        if process_commands_thread and process_commands_thread.is_alive():
            process_commands_thread.join(timeout=1)
            process_commands_thread = None

        if dm_cli_handler and dm_cli_handler.active_process:
            dm_cli_handler.stop_command()
        dm_cli_handler = None
        log_to_console("dm_cli_handler сброшен.")

        reset_test_state()
        reset_progress_bar()
    else:
        log_to_console("Нет активного процесса для остановки.")


def start_freeze():
    """Отправка команды для запуска охлаждения через dm-cli."""
    global dm_cli_handler, test_running

    # Получаем выбранный порт из выпадающего списка
    port = com_port_combobox.get()

    if not port:
        log_to_console("Выберите порт для подключения.")
        return

    # Проверяем, существует ли экземпляр dm_cli_handler
    if not dm_cli_handler:
        log_to_console("dm-cli не инициализирован.")
        return

    # Функция для запуска dm-cli в отдельном потоке
    def run_cooling_command():
        try:
            log_to_console(f"Запуск охлаждения через dm-cli на порту {port}...")
            dm_cli_handler.run_command(["test", "--port", port, "cooling.lua"])
            log_to_console("Охлаждение успешно завершено.")
        except Exception as e:
            log_to_console(f"Ошибка запуска охлаждения через dm-cli: {e}")
        finally:
            # Сбрасываем флаг выполнения после завершения процесса
            test_running.clear()
            reset_test_state()

    # Устанавливаем флаг выполнения
    test_running.set()

    # Запускаем команду в отдельном потоке
    cooling_thread = threading.Thread(target=run_cooling_command, daemon=True)
    cooling_thread.start()


def emergency_stop(event):
    """Экстренная остановка по нажатию клавиши."""
    log_to_console("Экстренная остановка: нажата клавиша 'Esc'.")
    stop_test()
    reset_test_state()

def reset_test_state():
    global current_rpm, previous_rpm, current_speed, previous_speed
    global current_avg_rpm, previous_avg_rpm, rpm_count
    global rpm_received, current_speed_check, test_target_speed
    global command_queue

    previous_rpm = []
    current_rpm = []
    current_speed = None
    previous_speed = None
    previous_avg_rpm = None
    current_avg_rpm = None
    rpm_count = 0
    rpm_received = False
    current_speed_check = 0
    test_target_speed = None

    with lock:
        while not command_queue.empty():
            command_queue.get()


def update_stand_name(stand_name):
    """Обновляет интерфейс в зависимости от выбранного стенда."""
    if stand_name == "шпиндель":
        engine_name_entry.config(state=tk.DISABLED)  # Отключаем поле ввода двигателя
        engine_name_label.config(text="")  # Скрываем метку поля
    else:
        engine_name_entry.config(state=tk.NORMAL)  # Включаем поле для других стендов
        engine_name_label.config(text="Двигатель:")  # Восстанавливаем метку


def close_application():
    """Закрытие приложения."""
    log_to_console("Закрытие приложения...")
    stop_event.set()
    if ser is not None and ser.is_open:
        ser.close()
        log_to_console("COM-порт закрыт.")
    root.destroy()


def update_progress_bar(speed):
    """Вычисляет и обновляет прогресс-бар на основе текущей скорости."""
    global test_target_speed, progress_complete

    if not test_running.is_set() or test_target_speed is None or progress_complete:
        return  # Тест не запущен или прогресс уже завершен

    # Определяем минимальную скорость (1000 RPM)
    min_speed = 1000

    # Вычисляем прогресс
    progress = ((speed - min_speed) / (test_target_speed - min_speed)) * 100

    # Ограничиваем прогресс до 100%
    if progress >= 100:
        progress = 100
        progress_complete = True

    # Обновляем прогресс-бар в главном потоке
    root.after(0, lambda: progress_var.set(progress))
    root.after(0, lambda: progress_label.config(
        text=f"Прогресс: {int(progress)}%"))

    # log_to_console(f"Текущая скорость: {speed} RPM. Прогресс: {int(progress)}%")

    if progress_complete:
        log_to_console("Прогресс достиг 100%.")
        # Дополнительные действия при достижении 100%, если необходимо


def reset_progress_bar():
    """Сбрасывает прогресс-бар до нуля."""
    global progress_complete
    progress_complete = False
    root.after(0, lambda: progress_var.set(0))
    root.after(0, lambda: progress_label.config(text="Прогресс: 0%"))


def update_com_ports():
    """Обновляет список доступных COM-портов."""
    try:
        com_ports = [port.device for port in serial.tools.list_ports.comports()]
        if not com_ports:
            log_to_console("Нет доступных COM-портов.")
        else:
            log_to_console(f"Обновленный список портов: {', '.join(com_ports)}")
        com_port_combobox['values'] = com_ports
        com_port_combobox.set("Выберите COM-порт")
    except Exception as e:
        log_to_console(f"Ошибка при обновлении списка портов: {e}")


# Основное окно
root = ThemedTk()
root.get_themes()  # Получаем доступные темы
root.set_theme("arc")  # Устанавливаем желаемую тему

root.title("Тестирование")

# Создаем вкладки
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill=tk.BOTH)

# Вкладка с тестом
test_frame = tk.Frame(notebook)
notebook.add(test_frame, text="Тест")

# Вкладка с настройками
settings_frame = tk.Frame(notebook)
notebook.add(settings_frame, text="Настройки")

# Создаем основную рамку для размещения элементов
main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(expand=True, fill=tk.BOTH)

# Поля для ввода названия двигателя и пропеллера в тестовой вкладке
input_frame = tk.Frame(test_frame)
input_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky='ew')

engine_name_label = tk.Label(input_frame, text="Название двигателя:")
engine_name_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
engine_name_entry = tk.Entry(input_frame)
engine_name_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

propeller_name_label = tk.Label(input_frame, text="Название пропеллера:")
propeller_name_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
propeller_name_entry = tk.Entry(input_frame)
propeller_name_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

# Лого в тестовой вкладке
try:
    image = Image.open("dron_motors.png")  # Загрузите изображение
    image = image.resize((250, 100), Image.Resampling.LANCZOS)
    logo_photo = ImageTk.PhotoImage(image)
    logo_label = tk.Label(test_frame, image=logo_photo)
    logo_label.grid(row=0, column=2, rowspan=2, padx=10, pady=5, sticky='n')
except FileNotFoundError:
    print("Изображение 'dron_motors.png' не найдено.")

input_frame.columnconfigure(1, weight=1)

# Ползунок для теста
speed_percent_label = tk.Label(test_frame, text="Процент разгона:")
speed_percent_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
speed_percent_slider = tk.Scale(test_frame, from_=10, to=100,
                                orient=tk.HORIZONTAL, length=300, resolution=10, tickinterval=10)
speed_percent_slider.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

# Прогресс бар и метка
progress_frame = tk.Frame(test_frame)
progress_frame.grid(row=2, column=0, columnspan=2, pady=(10, 10), sticky='ew')

progress_label = tk.Label(progress_frame, text="Прогресс: 0%")
progress_label.pack(anchor='w', padx=10)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(
    progress_frame, variable=progress_var, maximum=100)
progress_bar.pack(fill='x', padx=10, pady=5)

# Настройки COM-порта в тестовой вкладке
com_frame = tk.Frame(test_frame)
com_frame.grid(row=3, column=0, pady=10, sticky='w')

com_port_label = tk.Label(com_frame, text="Выберите COM-порт:")
com_port_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')

com_ports = [port.device for port in serial.tools.list_ports.comports()]
com_port_combobox = ttk.Combobox(com_frame, values=com_ports)
com_port_combobox.set("Выберите COM-порт")
com_port_combobox.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

com_frame.columnconfigure(1, weight=1)

# Новый фрейм для кнопок "Подключение к стенду" и "Информация о стенде"
connect_info_frame = tk.Frame(test_frame)
connect_info_frame.grid(row=3, column=1, padx=10, pady=10, sticky='e')

connect_button = ttk.Button(
    connect_info_frame, text="Подключение к стенду", command=connect_to_stand
)
connect_button.pack(side=tk.LEFT, padx=5, pady=5)

# Настройки на вкладке "Настройки"
pulse_threshold_label = tk.Label(
    settings_frame, text="Колличество пульсов\nна 10 оборотов\n(70 по умлочанию)")
pulse_threshold_label.grid(row=0, column=0, padx=10, pady=5, sticky='e')
pulse_threshold_entry = tk.Entry(settings_frame)
pulse_threshold_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
pulse_threshold_button = ttk.Button(
    settings_frame, text="Отправить", command=lambda x: x)
pulse_threshold_button.grid(row=0, column=2, padx=10, pady=5)

moment_tenz_label = tk.Label(
    settings_frame, text="Коэффициент момента\n(1 по умолчанию)")
moment_tenz_label.grid(row=1, column=0, padx=10, pady=5, sticky='e')
moment_tenz_entry = tk.Entry(settings_frame)
moment_tenz_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')
moment_tenz_button = ttk.Button(
    settings_frame, text="Отправить", command=lambda x: x)
moment_tenz_button.grid(row=1, column=2, padx=10, pady=5)

thrust_tenz_label = tk.Label(
    settings_frame, text="Коэффициент тяги\n(1 по умолчанию)")
thrust_tenz_label.grid(row=2, column=0, padx=10, pady=5, sticky='e')
thrust_tenz_entry = tk.Entry(settings_frame)
thrust_tenz_entry.grid(row=2, column=1, padx=10, pady=5, sticky='ew')
thrust_tenz_button = ttk.Button(
    settings_frame, text="Отправить", command=lambda x: x)
thrust_tenz_button.grid(row=2, column=2, padx=10, pady=5)

# Позволяет полю ввода растягиваться
settings_frame.columnconfigure(1, weight=1)

# Остальные кнопки управления остаются в button_frame
button_frame = tk.Frame(main_frame)
button_frame.grid(row=5, column=0, columnspan=3,
                  pady=(10, 0), sticky='ew', padx=10)

start_button = ttk.Button(button_frame, text="Запустить тест",
                          command=start_test, state=tk.DISABLED)
start_button.grid(row=0, column=0, padx=10, pady=5)

stop_button = ttk.Button(
    button_frame, text="Остановить тест", command=stop_test)
stop_button.grid(row=0, column=1, padx=10, pady=5)

start_freeze_button = ttk.Button(
    button_frame, text="Начать охлаждение", command=start_freeze)
start_freeze_button.grid(row=1, column=0, padx=10, pady=5)

stop_freeze_button = ttk.Button(
    button_frame, text="Остановить охлаждение", command=stop_test)
stop_freeze_button.grid(row=1, column=1, padx=10, pady=5)

refresh_ports_button = ttk.Button(
    connect_info_frame, text="Обновить список портов", command=update_com_ports
)
refresh_ports_button.pack(side=tk.LEFT, padx=5, pady=5)

# Инструкция пользователю
instruction_label = tk.Label(
    button_frame, text="Подключитесь к стенду перед началом теста.")
instruction_label.grid(row=2, column=0, columnspan=3,
                       padx=10, pady=5, sticky='w')

# Консольное окно
console_output = scrolledtext.ScrolledText(
    main_frame, wrap=tk.WORD, height=15, width=60, state=tk.DISABLED)
console_output.grid(row=6, column=0, columnspan=3,
                    padx=10, pady=10, sticky='nsew')

main_frame.columnconfigure(2, weight=1)  # Позволяет кнопкам растягиваться
# Позволяет консольному окну растягиваться
main_frame.rowconfigure(6, weight=1)

# Закрытие приложения
root.protocol("WM_DELETE_WINDOW", close_application)

# Привязка клавиши 'Esc' к экстренной остановке
root.bind('<Escape>', emergency_stop)

root.mainloop()
