"""Flask extensions - imported by app.py and db_models.py."""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Typed base class for SQLAlchemy models."""

    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
