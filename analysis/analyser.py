import numpy as np
from decimal import Decimal, InvalidOperation
import datetime


def average_columns(data_to_clean):
    try:
        print(data_to_clean)
        data_to_clean = delete_trash(data_to_clean)
        print("\n")
        print(data_to_clean)
    except Exception as e:
        print(f"Ошибка в delete_trash: {e}")
        return []

    try:
        result = []

        # Берем первый и второй столбцы из первой строки
        try:
            result.append(data_to_clean[0][0])  # Первый столбец
            result.append(data_to_clean[0][1])  # Второй столбец
            result.append(data_to_clean[0][2])  # Второй столбец
        except Exception as e:
            print(f"Ошибка при добавлении первых трех столбцов: {e}")
            return []

        # Вычисляем среднее для каждого столбца начиная с третьего
        try:
            for col_idx in range(3, len(data_to_clean[0])):
                column_sum = sum(row[col_idx] for row in data_to_clean)  # Суммируем значения в столбце
                column_avg = column_sum / len(data_to_clean)  # Среднее значение
                result.append(column_avg)  # Добавляем среднее в результат
        except Exception as e:
            print(f"Ошибка при вычислении среднего по столбцам: {e}")
            return []

    except Exception as e:
        print(f"Общая ошибка в average_columns: {e}")
        return []

    return result


def analyze_DB(test_pk, db_manager):
    try:
        test_data = db_manager.get_test_data(test_pk)
        if not test_data:
            print("Нет данных для обработки.")
            return
    except Exception as e:
        print(f"Ошибка при получении данных из базы: {e}")
        return

    try:
        current_throttle = None
        data_to_interpol = []

        for record in test_data:
            try:
                row_data = [
                    record.test_id_fk,  # integer
                    record.time,  # timestamp
                    record.throttle,  # smallint
                    record.moment if record.moment >= 0 else 0,  # numeric(10, 4)
                    record.thrust if record.thrust >= 0 else 0,  # smallint
                    record.rpm,  # integer
                    record.current,  # numeric(10, 4)
                    record.voltage,  # numeric(10, 4)
                    record.power,  # numeric(10, 4)
                    record.temperature,  # numeric(10, 4)
                    record.mech_power,  # numeric(10, 4)
                    record.efficiency  # numeric(10, 4)
                ]
            except Exception as e:
                print(f"Ошибка при формировании строки данных: {e}")
                continue

            # Инициализация значения current_throttle при первом проходе
            if current_throttle is None:
                current_throttle = record.throttle

            # Проверка на смену скорости (throttle)
            if record.throttle != current_throttle:
                # Анализ накопленных данных
                if data_to_interpol:
                    try:
                        cleaned_data = average_columns(data_to_interpol)
                    except Exception as e:
                        print(f"Ошибка при очистке данных и вычислении среднего: {e}")
                        return

                    try:
                        db_manager.add_test_clean(
                            cleaned_data[0],
                            cleaned_data[1],
                            cleaned_data[2],
                            cleaned_data[3],
                            cleaned_data[4],
                            cleaned_data[5],
                            cleaned_data[6],
                            cleaned_data[7],
                            cleaned_data[8],
                            cleaned_data[9],
                            cleaned_data[10],
                            cleaned_data[11]
                        )
                    except Exception as e:
                        print(f"Ошибка при добавлении очищенных данных в базу: {e}")

                # Переключение на новую скорость и очистка накопленных данных
                current_throttle = record.throttle
                data_to_interpol = []

            data_to_interpol.append(row_data)

        # Обработка оставшихся данных для последней группы скорости
        if data_to_interpol:
            try:
                cleaned_data = average_columns(data_to_interpol)
                db_manager.add_test_clean(
                    cleaned_data[0],
                    cleaned_data[1],
                    cleaned_data[2],
                    cleaned_data[3],
                    cleaned_data[4],
                    cleaned_data[5],
                    cleaned_data[6],
                    cleaned_data[7],
                    cleaned_data[8],
                    cleaned_data[9],
                    cleaned_data[10],
                    cleaned_data[11]
                )
            except Exception as e:
                print(f"Ошибка при добавлении оставшихся очищенных данных: {e}")

    except Exception as e:
        print(f"Общая ошибка в analyze_DB: {e}")


def delete_trash(data_to_interpol):
    try:
        if not data_to_interpol:
            print("Получен пустой список данных.")
            return []

        # Убираем строки с некорректными значениями
        valid_rows = [
            row for row in data_to_interpol
            if all(is_valid(value) for value in row[3:])
        ]
        if not valid_rows:
            print("Нет валидных строк (все строки некорректны).")
            return []  # Если все строки оказались некорректными

        print(f"Валидные строки: {valid_rows}")

        # Вычисляем среднее значение по каждому столбцу (с 4-го по последний)
        column_means = []
        num_columns = len(valid_rows[0])  # Количество столбцов
        for col_index in range(3, num_columns):
            column_values = [row[col_index] for row in valid_rows]
            # Для вычисления среднего исключаем некорректные значения (NaN, None и т.п.)
            valid_column_values = [value for value in column_values if is_valid(value)]
            if valid_column_values:
                mean_value = sum(valid_column_values) / len(valid_column_values)
                column_means.append(mean_value)
                print(f"Среднее для столбца {col_index}: {mean_value}")
            else:
                column_means.append(None)  # Если в столбце нет валидных значений
                print(f"В столбце {col_index} нет валидных значений.")

        # Фильтруем строки, проверяя отклонение от среднего на 5%
        result = []
        for row in data_to_interpol:
            if any(not is_valid(value) for value in row[3:]):
                print(f"Пропускаем строку {row} из-за некорректных значений.")
                continue  # Пропускаем строку, если она содержит некорректные значения

            invalid_row = False
            for col_index, value in enumerate(row[3:], start=3):
                mean_value = column_means[col_index - 3]  # Индекс столбца относительно среднего
                if mean_value is not None and abs(value - mean_value) / (mean_value+1) > 0.05:
                    invalid_row = True
                    print(f"Строка {row} отклоняется от среднего значения в столбце {col_index} на более чем 5%.")
                    break

            if not invalid_row:
                result.append(row)
                print(f"Строка {row} добавлена в результат.")

        print(f"Результат: {result}")
        return result

    except Exception as e:
        print(f"Ошибка в delete_trash: {e}")
        return []


def is_valid(value):
    """
    Проверяет, является ли значение допустимым.
    """
    try:
        if value is None:
            return False
        if isinstance(value, Decimal):
            if value.is_nan():
                return False
        if isinstance(value, float):
            if value != value:  # Проверка на NaN
                return False
        # Проверка на возможность преобразования в число
        if isinstance(value, (int, float, Decimal)):
            return True
        return False
    except (ValueError, TypeError, InvalidOperation):
        return False


def analyze_rpm(current_avg_rpm, previous_avg_rpm, current_speed, previous_speed, log_to_console, stop_test):
    """Анализирует средние RPM для текущей и предыдущей скорости."""
    if previous_avg_rpm is None or current_avg_rpm is None:
        return  # Недостаточно данных для анализа

    log_to_console(f"Сравнение RPM между скоростью {previous_speed} ({previous_avg_rpm:.2f}) "
                   f"и скоростью {current_speed} ({current_avg_rpm:.2f})")

    if current_avg_rpm <= previous_avg_rpm:
        log_to_console(
            "Среднее RPM на текущей скорости меньше, чем на предыдущей. Остановка теста.")
        #stop_test()
        return

    # Вычисляем процент изменения между RPM
    rpm_change_percent = abs((current_avg_rpm - previous_avg_rpm) / (previous_avg_rpm + 1.0)) * 100

    log_to_console(f"Изменение RPM: {rpm_change_percent:.2f}%")

    # Если изменение менее 4%, останавливаем тест
    if rpm_change_percent < 4:
        log_to_console("Слишком малый рост оборотов. Остановка теста.")
        #stop_test()


def analyze_current(current_values, current_speed, log_to_console, stop_test, max_current_threshold=10):
    """Анализирует значения тока и при необходимости останавливает тест."""
    if len(current_values) == 20:
        avg_current = sum(current_values) / len(current_values)
        log_to_console(f"Средний ток для скорости {current_speed}: {avg_current:.2f}")
        if avg_current > max_current_threshold:
            log_to_console("Средний ток превышает порог. Остановка теста.")
            #stop_test()


def analyze_temperature(temperature_values, current_speed, log_to_console, stop_test, max_temperature_threshold=80):
    """Анализирует значения температуры и при необходимости останавливает тест."""
    if len(temperature_values) == 20:
        avg_temperature = sum(temperature_values) / len(temperature_values)
        log_to_console(f"Средняя температура для скорости {current_speed}: {avg_temperature:.2f}")
        if avg_temperature > max_temperature_threshold:
            log_to_console("Средняя температура превышает порог. Остановка теста.")
        #stop_test()