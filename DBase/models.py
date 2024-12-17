from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Motor(Base):
    __tablename__ = "motors"
    motors_pk = Column(Integer, primary_key=True, autoincrement=True)
    producer = Column(String(255), nullable=False)
    model_name = Column(String(255), nullable=False)
    kv = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Motor(producer='{self.producer}', model_name='{self.model_name}', kv={self.kv})>"