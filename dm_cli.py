import subprocess
import platform
import psutil


class DMCLIHandler:
    """Класс для управления взаимодействием с dm-cli."""
    def __init__(self, log_callback):
        """
        :param log_callback: Функция для логирования (например, log_to_console).
        """
        self.log_callback = log_callback
        self.active_process = None  # Хранение активного процесса

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
        command = ["dm-cli.exe"] + args

        # Добавляем "./" для Unix-платформ
        if platform.system() != "Windows":
            command[0] = f"./dm-cli"
            command[16] = f"lua/{command[16].split("/")[-1]}"
            print(command)

        try:
            if platform.system() == "Windows":
                self.active_process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, encoding='utf-8', errors='replace'
                )
            else:
                self.active_process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if real_time:
                # Читаем вывод команды в реальном времени
                for line in iter(self.active_process.stdout.readline, ""):
                    self.log(line.strip())

                self.active_process.stdout.close()
                self.active_process.wait()

                # Обрабатываем ошибки
                if self.active_process.returncode != 0:
                    for line in iter(self.active_process.stderr.readline, ""):
                        self.log(line.strip())
                    self.active_process.stderr.close()

                return self.active_process.returncode

            else:
                stdout, stderr = self.active_process.communicate()
                self.log(stdout.strip())
                if self.active_process.returncode != 0:
                    self.log(stderr.strip())
                return self.active_process.returncode

        except Exception as e:
            print(f"Ошибка запуска dm-cli: {e}")
            return -1

    def stop_command(self):
        """Прерывает выполнение текущей команды dm-cli."""
        if self.active_process:
            if self.active_process.poll() is None:  # Процесс все еще активен
                self.log(f"Прерывание процесса dm-cli с PID {self.active_process.pid}...")

                try:
                    process = psutil.Process(self.active_process.pid)
                    for child in process.children(recursive=True):  # Убиваем всех детей
                        self.log(f"Убийство дочернего процесса PID {child.pid}")
                        child.terminate()
                    process.terminate()  # Убиваем основной процесс
                    process.wait(timeout=3)  # Ждем завершения процесса
                except Exception as e:
                    self.log(f"Ошибка при остановке процесса: {e}")
            else:
                self.log("Процесс dm-cli уже завершен.")
            self.active_process = None
        else:
            self.log("Нет активного процесса для прерывания.")

    def run_test(self, port, pulse_max, pulse_min, script, lopasti, tenz1, tenz2, tenz3):
        """
        Запускает тест с использованием dm-cli.
        :param pulse_min:
        :param lopasti: Колличество лопастей
        :param port: Порт для подключения.
        :param pulse_max: Значение pulseMax для теста.
        :param script: Название скрипта для выполнения.
        """
        args = [
                "test",
                "--args", f"pulseMax={pulse_max}",
                "--args", f"pulseMin={pulse_min}",
                "--args", f"tenz1={tenz1}",
                "--args", f"tenz2={tenz2}",
                "--args", f"tenz3={tenz3}",
                "--args", f"lopasti={lopasti}",
                "--port", port, script]
        print(args)
        self.run_command(args)

    def connect_to_stand(self, port, script):
        """
        Подключение к стенду с использованием dm-cli.
        :param port: Порт для подключения.
        :param script: Название скрипта для подключения.
        """
        args = ["test", "--port", port, script]
        self.run_command(args)