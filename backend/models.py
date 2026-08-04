from sqlalchemy import Column, Integer, String, Text, ARRAY
from database import Base
from pgvector.sqlalchemy import Vector


class Border(Base):
    __tablename__ = "borders"

    year = Column(Integer, primary_key=True, index=True)
    country_code = Column(String, primary_key=True, index=True)
    geojson = Column(String, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    source = Column(String, nullable=False)


class Moment(Base):
    __tablename__ = "moments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    region_codes = Column(ARRAY(String), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    citations = Column(ARRAY(String), nullable=True)
