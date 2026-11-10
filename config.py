import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-before-deployment"
    )

    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///" + os.path.join(
            BASE_DIR,
            "database",
            "stockpredict.db"
        ).replace("\\", "/")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False