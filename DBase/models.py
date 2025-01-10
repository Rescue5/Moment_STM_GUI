from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, TIMESTAMP, PrimaryKeyConstraint, Numeric, SmallInteger
from datetime import datetime, timezone

Base = declarative_base()


class Motor(Base):
    __tablename__ = "motors"
    motors_pk = Column(Integer, primary_key=True, autoincrement=True)
    producer = Column(String(255), nullable=False)
    model_name = Column(String(255), nullable=False)
    kv = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Motor(producer='{self.producer}', model_name='{self.model_name}', kv={self.kv})>"


class Propellers(Base):
    __tablename__ = "propellers"
    propellers_pk = Column(Integer, primary_key=True, autoincrement=True)
    producer = Column(String(255), nullable=False)
    diameter = Column(Integer, nullable=False)
    pitch = Column(Integer, nullable=False)
    blades = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Propellers(producer='{self.producer}', diameter='{self.diameter}', pitch='{self.pitch}', blades='{self.blades})>"


class Test(Base):
    __tablename__ = "tests"
    test_pk = Column(Integer, primary_key=True, autoincrement=True)
    motor_id_fk = Column(Integer, ForeignKey("motors.motors_pk"), nullable=False)
    propeller_id_fk = Column(Integer, ForeignKey("propellers.propellers_pk"), nullable=False)
    test_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Test(test_pk={self.test_pk}, motor_id_fk={self.motor_id_fk}, propeller_id_fk={self.propeller_id_fk}, test_date={self.test_date})>"


class RawTestData(Base):
    __tablename__ = "raw_tests_data"
    test_id_fk = Column(Integer, ForeignKey("tests.test_pk"), nullable=False)
    time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    throttle = Column(SmallInteger)
    moment = Column(Numeric(10, 4))
    thrust = Column(SmallInteger)
    rpm = Column(Integer)
    current = Column(Numeric(10, 4))
    voltage = Column(Numeric(10, 4))
    power = Column(Numeric(10, 4))
    temperature = Column(Numeric(10, 4))
    mech_power = Column(Numeric(10, 4))
    efficiency = Column(Numeric(10, 4))

    __table_args__ = (
        PrimaryKeyConstraint("test_id_fk", "time"),
    )

    def __repr__(self):
        return (
            f"<RawTestData(test_id_fk={self.test_id_fk},"
            f"throttle={self.throttle}, moment={self.moment}, thrust={self.thrust}, rpm={self.rpm}, "
            f"current={self.current}, voltage={self.voltage}, power={self.power}, "
            f"temperature={self.temperature}, mech_power={self.mech_power}, efficiency={self.efficiency})>"
        )


class CleanTestData(Base):
    __tablename__ = "clean_tests_data"
    test_id_fk = Column(Integer, ForeignKey("tests.test_pk"), nullable=False)
    time = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    throttle = Column(SmallInteger)
    moment = Column(Numeric(10, 4))
    thrust = Column(SmallInteger)
    rpm = Column(Integer)
    current = Column(Numeric(10, 4))
    voltage = Column(Numeric(10, 4))
    power = Column(Numeric(10, 4))
    temperature = Column(Numeric(10, 4))
    mech_power = Column(Numeric(10, 4))
    efficiency = Column(Numeric(10, 4))

    __table_args__ = (
        PrimaryKeyConstraint("test_id_fk", "time"),
    )

    def __repr__(self):
        return (
            f"<RawTestData(test_id_fk={self.test_id_fk},"
            f"throttle={self.throttle}, moment={self.moment}, thrust={self.thrust}, rpm={self.rpm}, "
            f"current={self.current}, voltage={self.voltage}, power={self.power}, "
            f"temperature={self.temperature}, mech_power={self.mech_power}, efficiency={self.efficiency})>"
        )