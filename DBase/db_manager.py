from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, Motor, Propellers

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
            return f"Ошибка при добавлении мотора: {e}"
        finally:
            session.close()

    def get_all_propellers(self):
        """Возвращает все двигатели из базы данных"""
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
        """Удаляет пропеллер по его producer, model и kv"""
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
                return f"Мотор {producer} {diameter}x{pitch}x{blades} удалён из базы данных!"
            else:
                return f"Мотор {producer} {diameter}x{pitch}x{blades} не найден в базе данных!"
        except Exception as e:
            session.rollback()
            return f"Ошибка при удалении мотора: {e}"
        finally:
            session.close()

