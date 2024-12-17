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
import sys
import datetime
import subprocess
import platform

from dm_cli import DMCLIHandler
from analyzer import analyze_rpm, analyze_current, analyze_temperature
from DBase.db_manager import DBManager

db_manager = DBManager()
dm_cli_handler = None

last_command = None


def get_project_root():
    """Возвращает путь к папке, где лежит exe или python файл."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


project_root = get_project_root()
tests_folder = os.path.join(project_root, 'tests')
lua_folder = os.path.join(project_root, 'lua')

manual_frame = False
settings_frame = False
test_frame_active = True

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

previous_avg_rpm = None  # Среднее RPM предыдущей скорости
current_avg_rpm = None  # Среднее RPM текущей скорости
rpm_count = 0  # Счетчик RPM для текущей скорости

test_target_speed = None  # Целевая скорость для текущего теста
progress_complete = False  # Флаг завершения прогресса

current_values = []  # Список для хранения значений тока на одной скорости
max_current_threshold = 900.0  # Установленный порог среднего значения тока

temperature_values = []  # Список для хранения значений температуры на одной скорости
max_temperature_threshold = 1000000  # Установленный порог среднего значения температуры

# Настройки
BAUD_RATE = 115200

ser = None  # Глобальная переменная для хранения объекта Serial
process_commands_thread = None  # Поток обработки команд
read_serial_thread = None  # Поток чтения данных

# Переменные для логирования
log_file = None
csv_file = None
log_file_lock = threading.Lock()

lopasti = 3

pulse_min = 800
pulse_max = 2200
test_percent = 10


def parse_and_save_to_csv(data):
    """Парсинг строки и запись в CSV + анализ некоторых данных"""
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
            moment, thrust, rpm, current, voltage, power, temperature, mech_power, kpd = (None,) * 9
            if stand_name in ["пропеллер", "момент", "шпиндель"]:
                if len(parts) >= 20:
                    moment = float(parts[3].strip())
                    thrust = int(parts[5].strip())
                    rpm = int(parts[7].strip())
                    current = float(parts[9].strip())
                    voltage = float(parts[11].strip())
                    power = float(parts[13].strip())
                    temperature = float(parts[15].strip())
                    mech_power = float(parts[17].strip())
                    kpd = float(parts[19].strip())
                else:
                    log_to_console(f"Недостаточно данных для {stand_name}: " + data)
                    return
            else:
                log_to_console("Неизвестный тип стенда.")
                return

            write_headers = False
            if test_running.is_set() and csv_file:
                if not os.path.exists(csv_file):
                    write_headers = True
                elif os.path.getsize(csv_file) == 0:
                    write_headers = True

                with log_file_lock:
                    with open(csv_file, 'a', newline='') as csvfile:
                        csv_writer = csv.writer(csvfile, delimiter=';')
                        if write_headers:
                            csv_writer.writerow(
                                ["Speed", "Moment", "Thrust", "RPM", "Current", "Voltage", "Power", "Temperature", "Mech.Power", "KPD"])
                        csv_writer.writerow([
                            str(speed).replace('.', ','),
                            str(moment).replace('.', ',') if moment is not None else "",
                            str(thrust).replace('.', ',') if thrust is not None else "",
                            str(rpm).replace('.', ',') if rpm is not None else "",
                            str(current).replace('.', ',') if current is not None else "",
                            str(voltage).replace('.', ',') if voltage is not None else "",
                            str(power).replace('.', ',') if power is not None else "",
                            str(temperature).replace('.', ',') if temperature is not None else "",
                            str(mech_power).replace('.', ',') if mech_power is not None else "",
                            str(kpd).replace('.', ',') if kpd is not None else ""
                        ])

            if current_speed != speed:
                current_values.clear()
                temperature_values.clear()
                if current_avg_rpm is not None:
                    previous_avg_rpm = current_avg_rpm

                previous_speed = current_speed
                current_speed = speed
                current_rpm = []
                rpm_count = 0
                current_avg_rpm = None

            if rpm is not None and not manual_frame:
                rpm_received = True
                current_rpm.append(rpm)
                rpm_count += 1

            if rpm_count == 20 and not manual_frame:
                current_avg_rpm = sum(current_rpm) / len(current_rpm)
                log_to_console(f"Среднее RPM для скорости {current_speed}: {current_avg_rpm:.2f}")
                analyze_rpm(current_avg_rpm, previous_avg_rpm, current_speed, previous_speed, log_to_console, stop_test)

            if current is not None and not manual_frame:
                current_values.append(current)
                analyze_current(current_values, current_speed, log_to_console, stop_test, max_current_threshold)

            if temperature is not None and not manual_frame:
                temperature_values.append(temperature)
                analyze_temperature(temperature_values, current_speed, log_to_console, stop_test, max_temperature_threshold)

        except (IndexError, ValueError) as e:
            log_to_console(f"Ошибка парсинга данных: {data} | Ошибка: {e}")


def connect_to_stand():
    """Выполняет команду для подключения к стенду через dm-cli и обрабатывает наименование стенда."""
    global ser, process_commands_thread, read_serial_thread, log_file, csv_file
    global stand_name
    port = com_port_combobox.get()
    script = os.path.join(lua_folder, "test_conn.lua")

    print(script)

    if not port:
        log_to_console("Выберите порт из выпадающего списка.")
        return

    if getattr(sys, 'frozen', False):  # Если программа собрана в exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    if platform.system() != "Windows":
        dm_cli_path = os.path.join(exe_dir, 'dm-cli')
    else:
        dm_cli_path = os.path.join(exe_dir, 'dm-cli.exe')

    print(exe_dir)
    print(dm_cli_path)

    command = [f"{dm_cli_path}", "test", "--port", port, script]

    if platform.system() != "Windows":
        command[0] = f"./dm-cli"
        command[4] = f"lua/test_conn.lua"
        print(command)
    try:
        if read_serial_thread is None or not read_serial_thread.is_alive():
            read_serial_thread = threading.Thread(
                target=read_output, daemon=True)
            read_serial_thread.start()

        if platform.system() == "Windows":
            result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
        else:
            result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0:
            # Ищем наименование стенда в выводе
            for line in result.stdout.splitlines():
                if "Наименование стенда:" in line:
                    stand_name = line.split(":")[1].strip().lower()
                    update_stand_name(stand_name)  # Вызываем функцию обновления интерфейса
                    log_to_console(f"Название стенда: {stand_name}")
                    log_to_console(f"Подключение к стенду успешно:\n{result.stdout}")

                    # Проверяем тип стенда
                    if stand_name in ["момент", "тяга", "шпиндель"]:
                        instruction_label.config(
                            text=f"Стенд: {stand_name.capitalize()}. Теперь можно запускать тест."
                        )
                        start_button.config(state=tk.NORMAL)
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
    global manual_frame, test_frame_active, settings_frame

    if settings_frame:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        settings_console_output.config(state=tk.NORMAL)
        settings_console_output.insert(tk.END, f"[{timestamp}] {message}\n")
        settings_console_output.yview(tk.END)
        settings_console_output.config(state=tk.DISABLED)
    elif manual_frame:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        manual_console_output.config(state=tk.NORMAL)
        manual_console_output.insert(tk.END, f"[{timestamp}] {message}\n")
        manual_console_output.yview(tk.END)
        manual_console_output.config(state=tk.DISABLED)
    else:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_console_output.config(state=tk.NORMAL)
        test_console_output.insert(tk.END, f"[{timestamp}] {message}\n")
        test_console_output.yview(tk.END)
        test_console_output.config(state=tk.DISABLED)
    # Также выводим в стандартный вывод для отладки
    print(f"[{timestamp}] {message}")


def read_output():
    """Читает данные из dm-cli и обрабатывает их в реальном времени."""
    global log_file, csv_file, stand_name, current_speed, current_speed_check, rpm_received, previous_speed

    while not stop_event.is_set():
        if dm_cli_handler and dm_cli_handler.active_process:
            try:
                line = dm_cli_handler.active_process.stdout.readline()
                if not line:
                    break
                data = line.strip()
                log_to_console(data)

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


def start_test():
    """Запуск теста."""
    global log_file, csv_file, stand_name, previous_rpm, current_rpm, current_speed, previous_speed, \
        previous_avg_rpm, current_avg_rpm, rpm_count, test_target_speed, progress_complete, dm_cli_handler
    global dm_cli_handler, read_serial_thread, process_commands_thread, lopasti
    global pulse_max, pulse_min

    reset_test_state()
    # Сбрасываем состояния
    stop_event.clear()
    test_running.clear()

    # Создаем новый экземпляр dm_cli_handler
    dm_cli_handler = DMCLIHandler(log_to_console)

    # Перезапускаем поток чтения данных
    if read_serial_thread is None or not read_serial_thread.is_alive():
        read_serial_thread = threading.Thread(target=read_output, daemon=True)
        read_serial_thread.start()

    propeller_name = propeller_name_entry.get()
    if stand_name != 'шпиндель':
        engine_name = engine_name_entry.get()
    else:
        engine_name = 'shpindel'

    if not engine_name or not propeller_name:
        log_to_console("Введите названия двигателя и пропеллера.")
        return

    # Составляем имена файлов для логов и CSV
    log_file = os.path.join(tests_folder,  f"{engine_name}_{propeller_name}_log.txt")
    csv_file = os.path.join(tests_folder,  f"{engine_name}_{propeller_name}_data.csv")

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

    test_target_speed = pulse_min + test_percent*10
    log_to_console(f"Целевая скорость установлена на {test_target_speed} RPM.")

    reset_progress_bar()

    port = com_port_combobox.get()
    if not port:
        log_to_console("Выберите порт для подключения.")
        return

    dm_cli_handler = DMCLIHandler(log_to_console)

    # Запускаем dm-cli в отдельном потоке
    script = os.path.join(lua_folder, "moment_test.lua")
    test_thread = threading.Thread(
        target=dm_cli_handler.run_test, args=(port, test_target_speed, pulse_min, script, lopasti), daemon=True
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
    global dm_cli_handler, test_running, lopasti, pulse_min

    # Сброс состояния и проверка порта
    reset_test_state()
    port = com_port_combobox.get()
    if not port:
        log_to_console("Выберите порт для подключения.")
        return

    # Создаем новый экземпляр dm_cli_handler, если нужно
    if not dm_cli_handler:
        dm_cli_handler = DMCLIHandler(log_to_console)

    # Устанавливаем флаг выполнения
    test_running.set()

    # Запускаем dm-cli в отдельном потоке
    script = os.path.join(lua_folder, "cooling.lua")
    cooling_thread = threading.Thread(
        target=dm_cli_handler.run_test, args=(port, 1200, pulse_min, script, lopasti), daemon=True
    )
    cooling_thread.start()

    log_to_console("Запуск охлаждения завершен.")


def set_max_current_threshold():
    """Устанавливает значение порога для среднего тока."""
    global max_current_threshold
    try:
        value = float(max_current_threshold_entry.get())
        max_current_threshold = value
        log_to_console(f"Порог среднего тока установлен на: {max_current_threshold}")
    except ValueError:
        log_to_console("Ошибка: Введите корректное число для порога тока.")


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

    current_values.clear()

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

    min_speed = 1000

    progress = ((speed - min_speed) / (test_target_speed - min_speed)) * 100

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


def set_lopasti():
    """Устанавливает значение для глобальной переменной lopasti."""
    global lopasti
    try:
        new_value = int(lopasti_entry.get())
        lopasti = new_value
        log_to_console(f"Значение lopasti изменено на: {lopasti}")
    except ValueError:
        log_to_console("Ошибка: введите целое число для lopasti.")


def update_pulse_values():
    """Обновляет значения pulse_min и pulse_max на основе положения ползунков."""
    global pulse_min, pulse_max

    # Получаем текущие значения ползунков
    new_min = speed_min_percent_slider.get()
    new_max = speed_max_percent_slider.get()

    # Если разница меньше или больше 1000, корректируем значения
    if (new_max - new_min) != 1000:
        if new_min + 1000 <= 2200:  # Если максимум не выходит за пределы
            new_max = new_min + 1000
        elif new_max - 1000 >= 800:  # Если минимум не выходит за пределы
            new_min = new_max - 1000

    # Устанавливаем значения с учетом границ
    if new_min < 800:
        new_min = 800
        new_max = new_min + 1000
    if new_max > 2200:
        new_max = 2200
        new_min = new_max - 1000

    # Устанавливаем значения ползунков
    speed_min_percent_slider.set(new_min)
    speed_max_percent_slider.set(new_max)

    # Обновляем глобальные переменные
    pulse_min = new_min
    pulse_max = new_max

    # Логируем обновление
    log_to_console(f"Обновлено: Минимальное значение ШИМ={pulse_min}, Максимальное значение ШИМ={pulse_max}")


def start_manual_monitoring():
    """Запуск мониторинга во вкладке 'Ручное управление'."""
    global dm_cli_handler, test_running, lopasti

    reset_test_state()
    port = com_port_combobox.get()
    log_to_console(port)
    if not port:
        log_to_console("Выберите порт для подключения.")
        return

    if not dm_cli_handler:
        dm_cli_handler = DMCLIHandler(log_to_console)

    test_running.set()

    try:
        script = os.path.join(lua_folder,"monitoring.lua")
        monitoring_thread = threading.Thread(
            target=dm_cli_handler.run_test,
            args=(port, 1200, 1200, script, lopasti),
            daemon=True
        )

        monitoring_thread.start()
        log_to_console("Запуск мониторинга")
    except Exception as e:
        log_to_console(f"Ошибка при запуске мониторинга: {e}")


def stop_manual_monitoring():
    """Остановка мониторинга во вкладке 'Ручное управление'."""
    global dm_cli_handler, test_running, read_serial_thread, process_commands_thread

    if test_running.is_set():
        log_to_console("Остановка мониторинга...")

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

        dm_cli_handler = None
        log_to_console("Мониторинг завершен.")
    else:
        log_to_console("Мониторинг не запущен.")

def update_frame(event):
    global manual_frame, settings_frame, test_frame_active
    """Скрыть элементы теста (main_frame и его содержимое), если активна вкладка 'Ручное управление'."""
    if notebook.tab(notebook.select(), "text") == "Ручное управление":
        manual_frame = True
        settings_frame = False
        test_frame_active = False
    elif notebook.tab(notebook.select(), "text") == "Тест":
        manual_frame = False
        settings_frame = False
        test_frame_active = True
    elif notebook.tab(notebook.select(), "text") == "Настройки":
        manual_frame = False
        settings_frame = True
        test_frame_active = False



def add_motor():
    producer = producer_entry.get()
    model = model_entry.get()
    kv = kv_entry.get()

    if not producer or not model or not kv.isdigit():
        log_to_console("Ошибка: Проверьте корректность введённых данных!")
        return

    db_message = db_manager.add_motor(producer, model, int(kv))
    log_to_console(db_message)
    update_motor_list()

    producer_entry.delete(0, tk.END)
    model_entry.delete(0, tk.END)
    kv_entry.delete(0, tk.END)

def update_motor_list():
    """Обновляет список двигателей из базы данных"""
    motors_listbox.delete(0, tk.END)  # Очистить список
    motors = db_manager.get_all_motors()
    for motor in motors:
        motors_listbox.insert(tk.END, f"{motor.producer}, {motor.model_name}, {motor.kv} KV")

def delete_motor():
    """Удаляет выбранный двигатель из базы данных"""
    try:
        selection = motors_listbox.get(motors_listbox.curselection())
        producer = (selection.split(",")[0]).strip(' ')
        model = (selection.split(",")[1]).strip(' ')
        kv = int((selection.split(",")[2]).split(" ")[1])
    except Exception as e:
        print(e)
        messagebox.showerror("Ошибка", "Пожалуйста, выберите двигатель для удаления.")
        return
    answer = messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите удалить двигатель {producer} {model} {kv}?")
    if answer:
        db_message = db_manager.delete_motor(producer, model, kv)
        print(db_message)
        update_motor_list()

root = ThemedTk()
root.get_themes()
root.set_theme("arc")

root.title("Тестирование")

# Создаем вкладки
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill=tk.BOTH)

# Вкладка с тестом
test_frame = tk.Frame(notebook)  # Устанавливаем фон для test_frame
notebook.add(test_frame, text="Тест")

# Вкладка с настройками
settings_frame = tk.Frame(notebook)
notebook.add(settings_frame, text="Настройки")

# Вкладка для ручного управления
manual_control_frame = tk.Frame(notebook)
notebook.add(manual_control_frame, text="Ручное управление")

# Вкладка для двигателей
motors_frame = tk.Frame(notebook)
notebook.add(motors_frame, text="Двигатели")

# # Создаем основную рамку для размещения элементов
# main_frame = tk.Frame(root, padx=10, pady=10)
# main_frame.pack(expand=True, fill=tk.BOTH)

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

def update_test_percent():
    global test_percent
    test_percent = test_percent_slider.get()
    log_to_console(f"Процент разгона: {test_percent}")

# Ползунок для процента разгона
test_percent_label = tk.Label(test_frame, text="Процент разгона")
test_percent_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')

test_percent_slider = tk.Scale(
    test_frame,
    from_=10,  # Начальное значение
    to=100,  # Максимальное значение
    orient=tk.HORIZONTAL,
    length=300,
    resolution=10,  # Шаг изменения
    tickinterval=10,  # Интервал для отметок
    command=lambda _: update_test_percent()
)
test_percent_slider.set(test_percent)  # Устанавливаем начальное значение
test_percent_slider.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

# Ползунок для максимального значения
speed_max_percent_label = tk.Label(settings_frame, text="Максимальное значение ШИМ:")
speed_max_percent_label.grid(row=4, column=0, padx=10, pady=5, sticky='w')

speed_max_percent_slider = tk.Scale(
    settings_frame,
    from_=800,  # Начальное значение
    to=2200,  # Максимальное значение
    orient=tk.HORIZONTAL,
    length=300,
    resolution=100,  # Шаг изменения
    tickinterval=150,  # Интервал для отметок
    command=lambda _: update_pulse_values()
)
speed_max_percent_slider.set(pulse_max)  # Устанавливаем начальное значение
speed_max_percent_slider.grid(row=4, column=1, padx=10, pady=5, sticky='ew')

# Ползунок для минимального значения
speed_min_percent_label = tk.Label(settings_frame, text="Минимальное значение ШИМ:")
speed_min_percent_label.grid(row=5, column=0, padx=10, pady=5, sticky='w')

speed_min_percent_slider = tk.Scale(
    settings_frame,
    from_=800,  # Начальное значение
    to=2200,  # Максимальное значение
    orient=tk.HORIZONTAL,
    length=300,
    resolution=100,  # Шаг изменения
    tickinterval=150,  # Интервал для отметок
    command=lambda _: update_pulse_values()
)
speed_min_percent_slider.set(pulse_min)  # Устанавливаем начальное значение
speed_min_percent_slider.grid(row=5, column=1, padx=10, pady=5, sticky='ew')

# Прогресс бар и метка
progress_frame = tk.Frame(test_frame)
progress_frame.grid(row=3, column=0, columnspan=2, pady=(10, 10), sticky='ew')

progress_label = tk.Label(progress_frame, text="Прогресс: 0%")
progress_label.pack(anchor='w', padx=10)

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(
    progress_frame, variable=progress_var, maximum=100)
progress_bar.pack(fill='x', padx=10, pady=5)

# Настройки COM-порта в тестовой вкладке
com_frame = tk.Frame(test_frame)
com_frame.grid(row=4, column=0, pady=10, sticky='w')

com_port_label = tk.Label(com_frame, text="Выберите COM-порт:")
com_port_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')

com_ports = [port.device for port in serial.tools.list_ports.comports()]
com_port_combobox = ttk.Combobox(com_frame, values=com_ports)
com_port_combobox.set("Выберите COM-порт")
com_port_combobox.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

com_frame.columnconfigure(1, weight=1)

# Новый фрейм для кнопок "Подключение к стенду" и "Информация о стенде"
connect_info_frame = tk.Frame(test_frame)
connect_info_frame.grid(row=4, column=1, padx=10, pady=10, sticky='e')

connect_button = ttk.Button(
    connect_info_frame, text="Подключение к стенду", command=connect_to_stand
)
connect_button.pack(side=tk.LEFT, padx=5, pady=5)

# Настройки на вкладке "Настройки"
# Макисмальный ток
max_current_threshold_label = tk.Label(
    settings_frame, text="Порог среднего тока\n(по умолчанию 90.0)")
max_current_threshold_label.grid(row=0, column=0, padx=10, pady=5, sticky='e')

max_current_threshold_entry = tk.Entry(settings_frame)
max_current_threshold_entry.insert(0, "90.0")  # Значение по умолчанию
max_current_threshold_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')

max_current_threshold_button = ttk.Button(
    settings_frame, text="Установить", command=set_max_current_threshold)
max_current_threshold_button.grid(row=0, column=2, padx=10, pady=5)

# Настройки lopasti
lopasti_label = tk.Label(
    settings_frame, text="Количество лопастей\n(3 по умолчанию)")
lopasti_label.grid(row=1, column=0, padx=10, pady=5, sticky='e')

lopasti_entry = tk.Entry(settings_frame)
lopasti_entry.insert(0, "3")
lopasti_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

lopasti_button = ttk.Button(
    settings_frame, text="Установить", command=set_lopasti)
lopasti_button.grid(row=1, column=2, padx=10, pady=5)

settings_frame.columnconfigure(1, weight=1)

button_frame = tk.Frame(test_frame)
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
    button_frame, text="Остановить охлаждение", command=emergency_stop)
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

# Консольное окно в тест
test_console_output = scrolledtext.ScrolledText(
    test_frame, wrap=tk.WORD, height=15, width=60, state=tk.DISABLED)
test_console_output.grid(row=6, column=0, columnspan=3,
                    padx=10, pady=10, sticky='nsew')

# Консольное окно в настройках
settings_console_output = scrolledtext.ScrolledText(
    settings_frame, wrap=tk.WORD, height=30, width=60, state=tk.DISABLED)
settings_console_output.grid(row=6, column=0, columnspan=3,
                    padx=10, pady=10, sticky='nsew')

# Консольное окно в ручном управлении
manual_console_output = scrolledtext.ScrolledText(
    manual_control_frame, wrap=tk.WORD, height=15, width=60, state=tk.DISABLED
)
manual_console_output.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

# Фрейм для кнопок управления
manual_buttons_frame = tk.Frame(manual_control_frame)
manual_buttons_frame.pack(pady=10, fill=tk.X)

# Кнопки для ручного управления
ttk.Button(
    manual_buttons_frame,
    text="Начать мониторинг",
    command=start_manual_monitoring
).pack(side=tk.LEFT, padx=10)

ttk.Button(
    manual_buttons_frame,
    text="Завершить мониторинг",
    command=stop_manual_monitoring
).pack(side=tk.LEFT, padx=10)

ttk.Button(
    manual_buttons_frame,
    text="Начать логирование",
    command=lambda: log_to_console("Логирование начато")
).pack(side=tk.LEFT, padx=10)

ttk.Button(
    manual_buttons_frame,
    text="Завершить логирование",
    command=lambda: log_to_console("Логирование завершено")
).pack(side=tk.LEFT, padx=10)

notebook.bind("<<NotebookTabChanged>>", update_frame)
update_frame(None)

# Поля для добавления двигателя
add_motor_frame = tk.Frame(motors_frame, padx=10, pady=10)
add_motor_frame.pack(fill=tk.X, pady=(0, 10))

producer_label = tk.Label(add_motor_frame, text="Производитель:")
producer_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
producer_entry = tk.Entry(add_motor_frame)
producer_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

model_label = tk.Label(add_motor_frame, text="Модель:")
model_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
model_entry = tk.Entry(add_motor_frame)
model_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

kv_label = tk.Label(add_motor_frame, text="KV:")
kv_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
kv_entry = tk.Entry(add_motor_frame)
kv_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

add_motor_frame.columnconfigure(1, weight=1)

add_motor_button = ttk.Button(add_motor_frame, text="Добавить двигатель", command=add_motor)
# add_motor_button = ttk.Button(add_motor_frame, text="Добавить двигатель", command=lambda x:x)
add_motor_button.grid(row=3, column=0, columnspan=2, pady=10)

# Список двигателей
motors_list_frame = tk.Frame(motors_frame, padx=10, pady=10)
motors_list_frame.pack(fill=tk.BOTH, expand=True)

# Обновляемая строка с меткой и кнопкой
header_frame = tk.Frame(motors_list_frame)
header_frame.pack(fill=tk.X)

motors_list_label = tk.Label(header_frame, text="Список двигателей:")
motors_list_label.pack(side=tk.LEFT, padx=5, pady=(0, 5))

refresh_motor_button = ttk.Button(header_frame, text="Обновить список", command=update_motor_list)
# refresh_motor_button = ttk.Button(header_frame, text="Обновить список", command=lambda x:x)
refresh_motor_button.pack(side=tk.LEFT, padx=5, pady=(0, 5))

# Список двигателей
motors_listbox = tk.Listbox(motors_list_frame, height=15)
motors_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

delete_motor_button = ttk.Button(motors_list_frame, text="Удалить двигатель", command=delete_motor)
# delete_motor_button = ttk.Button(motors_list_frame, text="Удалить двигатель", command=lambda x:x)
delete_motor_button.pack(pady=5)

#
# ВКЛАДКА С ПРОПЕЛЛЛЕРАМИ
#
def add_propeller():
    producer = propeller_producer_entry.get()
    diameter = diameter_entry.get()
    pitch = pitch_entry.get()
    blades = blade_entry.get()

    if not producer or not diameter.isdigit() or not pitch.isdigit() or not blades.isdigit():
        log_to_console("Ошибка: Проверьте корректность введённых данных!")
        return

    db_message = db_manager.add_propeller(producer, int(diameter), int(pitch), int(blades))
    log_to_console(db_message)
    update_propeller_list()

    propeller_producer_entry.delete(0, tk.END)
    diameter_entry.delete(0, tk.END)
    pitch_entry.delete(0, tk.END)
    blade_entry.delete(0,tk.END)


def update_propeller_list():
    """Обновляет список двигателей из базы данных"""
    propellers_listbox.delete(0, tk.END)  # Очистить список
    propellers = db_manager.get_all_propellers()
    for propeller in propellers:
        propellers_listbox.insert(tk.END, f"{propeller.producer}, {propeller.diameter}, {propeller.pitch}, {propeller.blades}")


def delete_propeller():
    """Удаляет выбранный двигатель из базы данных"""
    try:
        selection = propellers_listbox.get(propellers_listbox.curselection())
        producer = (selection.split(",")[0]).strip(' ')
        diameter = float((selection.split(",")[1]).strip(' '))
        pitch = float((selection.split(",")[2]).strip(' '))
        blades = int((selection.split(",")[3]).strip(' '))

    except Exception as e:
        print(e)
        messagebox.showerror("Ошибка", "Пожалуйста, выберите пропеллер для удаления.")
        return
    answer = messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите удалить пропеллер {producer} {diameter}x{pitch}x{blades}?")
    if answer:
        db_message = db_manager.delete_propeller(producer, diameter, pitch, blades)
        print(db_message)
        update_propeller_list()

propeller_frame = tk.Frame(notebook)
notebook.add(propeller_frame, text="Пропеллеры")

# Поля для добавления пропеллера
add_propeller_frame = tk.Frame(propeller_frame, padx=10, pady=10)
add_propeller_frame.pack(fill=tk.X, pady=(0, 10))

propeller_producer_label = tk.Label(add_propeller_frame, text="Производитель:")
propeller_producer_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')
propeller_producer_entry = tk.Entry(add_propeller_frame)
propeller_producer_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

diameter_label = tk.Label(add_propeller_frame, text="Диаметр:")
diameter_label.grid(row=1, column=0, padx=5, pady=5, sticky='w')
diameter_entry = tk.Entry(add_propeller_frame)
diameter_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

pitch_label = tk.Label(add_propeller_frame, text="Шаг:")
pitch_label.grid(row=2, column=0, padx=5, pady=5, sticky='w')
pitch_entry = tk.Entry(add_propeller_frame)
pitch_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

blade_label = tk.Label(add_propeller_frame, text="Лопасти:")
blade_label.grid(row=3, column=0, padx=5, pady=5, sticky='w')
blade_entry = tk.Entry(add_propeller_frame)
blade_entry.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

add_propeller_frame.columnconfigure(1, weight=1)

add_propeller_button = ttk.Button(add_propeller_frame, text="Добавить пропеллер", command=add_propeller)
# add_propeller_button = ttk.Button(add_propeller_frame, text="Добавить пропеллер", command=lambda x:x)
add_propeller_button.grid(row=4, column=0, columnspan=2, pady=10)

# Список пропеллеров
propellers_list_frame = tk.Frame(propeller_frame, padx=10, pady=10)
propellers_list_frame.pack(fill=tk.BOTH, expand=True)

# Обновляемая строка с меткой и кнопкой
propeller_header_frame = tk.Frame(propellers_list_frame)
propeller_header_frame.pack(fill=tk.X)

propellers_list_label = tk.Label(propeller_header_frame, text="Список пропеллеров:")
propellers_list_label.pack(side=tk.LEFT, padx=5, pady=(0, 5))

refresh_propeller_button = ttk.Button(propeller_header_frame, text="Обновить список", command=update_propeller_list)
# refresh_propeller_button = ttk.Button(propeller_header_frame, text="Обновить список", command=lambda x:x)
refresh_propeller_button.pack(side=tk.LEFT, padx=5, pady=(0, 5))

# Список пропеллеров
propellers_listbox = tk.Listbox(propellers_list_frame, height=15)
propellers_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

delete_propeller_button = ttk.Button(propellers_list_frame, text="Удалить пропеллер", command=delete_propeller)
# delete_propeller_button = ttk.Button(propellers_list_frame, text="Удалить пропеллер", command=lambda x:x)
delete_propeller_button.pack(pady=5)

test_frame.columnconfigure(2, weight=1)

# Позволяет консольному окну растягиваться
test_frame.rowconfigure(6, weight=1)

# Закрытие приложения
root.protocol("WM_DELETE_WINDOW", close_application)

# Привязка клавиши 'Esc' к экстренной остановке
root.bind('<Escape>', emergency_stop)

root.mainloop()