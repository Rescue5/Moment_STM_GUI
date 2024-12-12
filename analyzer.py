def analyze_rpm(current_avg_rpm, previous_avg_rpm, current_speed, previous_speed, log_to_console, stop_test):
    """Анализирует средние RPM для текущей и предыдущей скорости."""
    if previous_avg_rpm is None or current_avg_rpm is None:
        return  # Недостаточно данных для анализа

    log_to_console(f"Сравнение RPM между скоростью {previous_speed} ({previous_avg_rpm:.2f}) "
                   f"и скоростью {current_speed} ({current_avg_rpm:.2f})")

    if current_avg_rpm <= previous_avg_rpm:
        log_to_console(
            "Среднее RPM на текущей скорости меньше, чем на предыдущей. Остановка теста.")
        stop_test()
        return

    # Вычисляем процент изменения между RPM
    rpm_change_percent = abs((current_avg_rpm - previous_avg_rpm) / (previous_avg_rpm + 1.0)) * 100

    log_to_console(f"Изменение RPM: {rpm_change_percent:.2f}%")

    # Если изменение менее 4%, останавливаем тест
    if rpm_change_percent < 4:
        log_to_console("Слишком малый рост оборотов. Остановка теста.")
        stop_test()


def analyze_current(current_values, current_speed, log_to_console, stop_test, max_current_threshold=10):
    """Анализирует значения тока и при необходимости останавливает тест."""
    if len(current_values) == 20:
        avg_current = sum(current_values) / len(current_values)
        log_to_console(f"Средний ток для скорости {current_speed}: {avg_current:.2f}")
        if avg_current > max_current_threshold:
            log_to_console("Средний ток превышает порог. Остановка теста.")
            stop_test()


def analyze_temperature(temperature_values, current_speed, log_to_console, stop_test, max_temperature_threshold=80):
    """Анализирует значения температуры и при необходимости останавливает тест."""
    if len(temperature_values) == 20:
        avg_temperature = sum(temperature_values) / len(temperature_values)
        log_to_console(f"Средняя температура для скорости {current_speed}: {avg_temperature:.2f}")
        if avg_temperature > max_temperature_threshold:
            log_to_console("Средняя температура превышает порог. Остановка теста.")
            stop_test()