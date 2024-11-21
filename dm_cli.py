import subprocess
import platform

class DMCLIHandler:
    """Класс для управления взаимодействием с dm-cli."""

    def __init__(self, log_callback):
        """
        :param log_callback: Функция для логирования (например, log_to_console).
        """
        self.log_callback = log_callback

    def log(self, message):
        """Вывод сообщения в лог."""
        if self.log_callback:
            self.log_callback(message)

    def run_command(self, args, real_time=True):
        """
        Запускает команду dm-cli.
        :param args: Список аргументов команды.
        :param real_time: Если True, вывод команды записывается в реальном времени.
        :return: Код завершения команды.
        """
        command = ["dm-cli"] + args

        # Добавляем "./" для Unix-платформ
        if platform.system() != "Windows":
            command[0] = f"./{command[0]}"

        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            if real_time:
                # Читаем вывод команды в реальном времени
                for line in iter(process.stdout.readline, ""):
                    self.log(line.strip())

                process.stdout.close()
                process.wait()

                # Обрабатываем ошибки
                if process.returncode != 0:
                    for line in iter(process.stderr.readline, ""):
                        self.log(line.strip())
                    process.stderr.close()

                return process.returncode

            else:
                stdout, stderr = process.communicate()
                self.log(stdout.strip())
                if process.returncode != 0:
                    self.log(stderr.strip())
                return process.returncode

        except Exception as e:
            self.log(f"Ошибка запуска dm-cli: {e}")
            return -1

    def run_test(self, port, pulse_max, script):
        """
        Запускает тест с использованием dm-cli.
        :param port: Порт для подключения.
        :param pulse_max: Значение pulseMax для теста.
        :param script: Название скрипта для выполнения.
        """
        args = ["test", "--args", f"pulseMax={pulse_max}", "--port", port, script]
        self.run_command(args)

    def connect_to_stand(self, port, script):
        """
        Подключение к стенду с использованием dm-cli.
        :param port: Порт для подключения.
        :param script: Название скрипта для подключения.
        """
        args = ["test", "--port", port, script]
        self.run_command(args)