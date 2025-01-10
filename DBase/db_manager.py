from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from .models import Base, Motor, Propellers, Test, RawTestData, CleanTestData
from sqlalchemy.exc import IntegrityError


class DBManager:
    def __init__(self, db_url="postgresql://user:user@localhost:5432/DronMotors_Data"):
        """Инициализация подключения к БД"""
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def add_motor(self, producer, model_name, kv):
        """Добавляет мотор в базу данных"""
        session = self.Session()
        try:
            new_motor = Motor(producer=producer, model_name=model_name, kv=kv)
            session.add(new_motor)
            session.commit()
            return f"Мотор {model_name} добавлен в базу данных!"
        except Exception as e:
            session.rollback()
            return f"Ошибка при добавлении мотора: {e}"
        finally:
            session.close()

    def get_motor_id(self, producer, model_name, kv):
        """Получает ID двигателя по полям producer, model_name, kv"""
        session = self.Session()
        try:
            motor = session.query(Motor).filter(
                Motor.producer == producer,
                Motor.model_name == model_name,
                Motor.kv == kv
            ).first()
            return motor.motors_pk if motor else None
        except Exception as e:
            print(f"Ошибка при получении ID двигателя: {e}")
            return None
        finally:
            session.close()

    def get_all_motors(self):
        """Возвращает все двигатели из базы данных"""
        session = self.Session()
        try:
            motors = session.query(Motor).all()
            return motors
        except Exception as e:
            print(f"Ошибка при получении списка моторов: {e}")
            return []
        finally:
            session.close()

    def delete_motor(self, producer, model_name, kv):
        """Удаляет мотор по его producer, model и kv"""
        session = self.Session()
        try:
            motor_to_delete = session.query(Motor).filter_by(
                producer=producer,
                model_name=model_name,
                kv=kv
            ).first()

            if motor_to_delete:
                session.delete(motor_to_delete)
                session.commit()
                return f"Мотор {model_name} удалён из базы данных!"
            else:
                return f"Мотор {model_name} не найден в базе данных!"
        except Exception as e:
            session.rollback()
            return f"Ошибка при удалении мотора: {e}"
        finally:
            session.close()

    def add_propeller(self, producer, diameter, pitch, blades):
        """Добавляет пропеллер в базу данных"""
        session = self.Session()
        try:
            new_propeller = Propellers(producer=producer, diameter=diameter, pitch=pitch, blades=blades)
            session.add(new_propeller)
            session.commit()
            return f"Пропеллер {new_propeller} добавлен в базу данных!"
        except Exception as e:
            session.rollback()
            return f"Ошибка при добавлении пропеллера: {e}"
        finally:
            session.close()

    def get_propeller_id(self, producer, diameter, pitch, blades):
        """Получает ID пропеллера по полям producer, diameter, pitch, blades"""
        session = self.Session()
        try:
            propeller = session.query(Propellers).filter(
                Propellers.producer == producer,
                Propellers.diameter == diameter,
                Propellers.pitch == pitch,
                Propellers.blades == blades
            ).first()
            return propeller.propellers_pk if propeller else None
        except Exception as e:
            print(f"Ошибка при получении ID пропеллера: {e}")
            return None
        finally:
            session.close()

    def get_all_propellers(self):
        """Возвращает все пропеллеры из базы данных"""
        session = self.Session()
        try:
            propellers = session.query(Propellers).all()
            return propellers
        except Exception as e:
            print(f"Ошибка при получении списка пропеллеров: {e}")
            return []
        finally:
            session.close()

    def delete_propeller(self, producer, diameter, pitch, blades):
        """Удаляет пропеллер по его producer, diameter, pitch, blades"""
        session = self.Session()
        try:
            propeller_to_delete = session.query(Propellers).filter_by(
                producer=producer,
                diameter=diameter,
                pitch=pitch,
                blades=blades
            ).first()

            if propeller_to_delete:
                session.delete(propeller_to_delete)
                session.commit()
                return f"Пропеллер {producer} {diameter}x{pitch}x{blades} удалён из базы данных!"
            else:
                return f"Пропеллер {producer} {diameter}x{pitch}x{blades} не найден в базе данных!"
        except Exception as e:
            session.rollback()
            return f"Ошибка при удалении пропеллера: {e}"
        finally:
            session.close()

    def create_test_record(self, motor_id, propeller_id):
        """Добавляет запись в таблицу tests"""
        session = self.Session()
        try:
            new_test = Test(
                motor_id_fk=motor_id,
                propeller_id_fk=propeller_id
            )
            session.add(new_test)
            session.commit()
            return new_test.test_pk
        except Exception as e:
            session.rollback()
            return f"Ошибка при добавлении записи теста: {e}"
        finally:
            session.close()

    def add_test_row(self, test_id_fk, throttle, moment, thrust, rpm, current, voltage, power, temperature,
                     mech_power, efficiency):
        """Добавляет строку сырых данных теста в базу данных"""
        session = self.Session()
        try:
            new_test_row = RawTestData(
                test_id_fk=test_id_fk,
                throttle=throttle,
                moment=moment,
                thrust=thrust,
                rpm=rpm,
                current=current,
                voltage=voltage,
                power=power,
                temperature=temperature,
                mech_power=mech_power,
                efficiency=efficiency
            )
            session.add(new_test_row)
            session.commit()
            print(f"Строка сырых данных для теста {test_id_fk} добавлена в базу данных!")
            return f"Строка сырых данных для теста {test_id_fk} добавлена в базу данных!"
        except IntegrityError as e:
            session.rollback()
            print(f"Ошибка при добавлении строки сырых данных: {e}")
            return f"Ошибка при добавлении строки сырых данных: {e}"
        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении строки сырых данных: {e}")
            return f"Ошибка при добавлении строки сырых данных: {e}"
        finally:
            print("snus")
            session.close()

    def add_test_clean(self, test_id_fk, time, throttle, moment, thrust, rpm, current, voltage, power, temperature,
                       mech_power, efficiency):
        """Добавляет строку чистых данных теста в базу данных"""
        session = self.Session()
        try:
            new_test_row = CleanTestData(
                test_id_fk=test_id_fk,
                time=time,
                throttle=throttle,
                moment=moment,
                thrust=thrust,
                rpm=rpm,
                current=current,
                voltage=voltage,
                power=power,
                temperature=temperature,
                mech_power=mech_power,
                efficiency=efficiency
            )
            session.add(new_test_row)
            session.commit()
            print(f"Строка сырых данных для теста {test_id_fk} добавлена в базу данных!")
            return f"Строка сырых данных для теста {test_id_fk} добавлена в базу данных!"
        except IntegrityError as e:
            session.rollback()
            print(f"Ошибка при добавлении строки сырых данных: {e}")
            return f"Ошибка при добавлении строки сырых данных: {e}"
        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении строки сырых данных: {e}")
            return f"Ошибка при добавлении строки сырых данных: {e}"
        finally:
            print("snus")
            session.close()

    def get_test_data(self, test_pk):
        session = self.Session()
        try:
            test_data = session.query(RawTestData).filter(RawTestData.test_id_fk == test_pk).order_by(
                RawTestData.time).all()
            return test_data
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_cleaned_test_data(self, test_pk):
        session = self.Session()
        try:
            test_data = session.query(CleanTestData).filter(CleanTestData.test_id_fk == test_pk).order_by(CleanTestData.time).all()
            return test_data
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()


    def get_all_test(self):
        session = self.Session()
        try:
            tests = session.query(Test).order_by(desc(Test.test_date)).all()
            return tests
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_motor_by_id(self, motor_id):
        session = self.Session()
        try:
            motor = session.query(Motor).filter(Motor.motors_pk == motor_id).first()
            return motor
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def get_propeller_by_id(self, propeller_id):
        session = self.Session()
        try:
            propeller = session.query(Propellers).filter(Propellers.propellers_pk == propeller_id).first()
            return propeller
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

