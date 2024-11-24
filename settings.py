def send_pulse_threshold():
    """Отправка команды для настройки PULSE_THRESHOLD."""
    value = pulse_threshold_entry.get().strip()
    if value.isdigit() and int(value) > 0:
        command = f"PULSE_THRESHOLD_{value}"
        command_queue.put(command)
    else:
        messagebox.showerror(
            "Ошибка ввода", "Введите корректное положительное целое число для PULSE_THRESHOLD.")


def send_moment_tenz():
    """Отправка команды для настройки MOMENT_TENZ."""
    try:
        value = float(moment_tenz_entry.get().strip())
        if value > 0:
            command = f"MOMENT_TENZ_{value}"
            command_queue.put(command)
        else:
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Ошибка ввода", "Введите корректное положительное число для MOMENT_TENZ.")


def send_thrust_tenz():
    """Отправка команды для настройки THRUST_TENZ."""
    try:
        value = float(thrust_tenz_entry.get().strip())
        if value > 0:
            command = f"THRUST_TENZ_{value}"
            command_queue.put(command)
        else:
            raise ValueError
    except ValueError:
        messagebox.showerror(
            "Ошибка ввода", "Введите корректное положительное число для THRUST_TENZ.")