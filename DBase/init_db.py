import psycopg2
from psycopg2 import sql

# Параметры подключения к PostgreSQL
DB_NAME = "DronMotors_Data"
DB_USER = "user"
DB_PASSWORD = "user"
DB_HOST = "localhost"
DB_PORT = 5432

# SQL-скрипт для создания таблиц
CREATE_TABLES_SQL = """
-- Таблица двигателей
CREATE TABLE IF NOT EXISTS motors (
    motors_pk SERIAL PRIMARY KEY,
    producer VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    kv INTEGER NOT NULL
);

-- Таблица пропеллеров
CREATE TABLE IF NOT EXISTS propellers (
    propellers_pk SERIAL PRIMARY KEY,
    producer VARCHAR(255) NOT NULL,
    diameter FLOAT NOT NULL,
    pitch FLOAT NOT NULL,
    blades INTEGER NOT NULL
);

-- Таблица тестов
CREATE TABLE IF NOT EXISTS tests (
    test_pk SERIAL PRIMARY KEY,
    motor_id_fk INTEGER NOT NULL REFERENCES motors(motors_pk),
    propeller_id_fk INTEGER NOT NULL REFERENCES propellers(propellers_pk),
    test_date DATE NOT NULL
);

-- Таблица сырых данных тестов
CREATE TABLE IF NOT EXISTS raw_tests_data (
    test_id_fk INTEGER NOT NULL REFERENCES tests(test_pk),
    time FLOAT NOT NULL,
    throttle FLOAT,
    moment FLOAT,
    thrust FLOAT,
    rpm FLOAT,
    current FLOAT,
    voltage FLOAT,
    power FLOAT,
    temperature FLOAT,
    mech_power FLOAT,
    efficiency FLOAT,
    PRIMARY KEY (test_id_fk, time)
);

-- Таблица очищенных данных тестов
CREATE TABLE IF NOT EXISTS clean_tests_data (
    test_id_fk INTEGER NOT NULL REFERENCES tests(test_pk),
    time FLOAT NOT NULL,
    throttle FLOAT,
    moment FLOAT,
    thrust FLOAT,
    rpm FLOAT,
    current FLOAT,
    voltage FLOAT,
    power FLOAT,
    temperature FLOAT,
    mech_power FLOAT,
    efficiency FLOAT,
    PRIMARY KEY (test_id_fk, time)
);
"""

def initialize_database():
    try:
        # Подключаемся к базе данных
        print("Connecting to the database...")
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.autocommit = True
        print("Connected to the database successfully.")

        # Выполняем создание таблиц
        with conn.cursor() as cursor:
            print("Initializing the database...")
            cursor.execute(CREATE_TABLES_SQL)
            print("Database initialized successfully!")

    except psycopg2.Error as e:
        print("Error while initializing the database:", e)
    finally:
        if conn:
            conn.close()
            print("Connection closed.")

if __name__ == "__main__":
    initialize_database()