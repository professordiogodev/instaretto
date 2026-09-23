import os

from flask import Flask

from app.extensions import db
from app.logging_setup import configure_logging


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["S3_BUCKET_UPLOADS"] = os.environ["S3_BUCKET_UPLOADS"]
    app.config["S3_BUCKET_LOGS"] = os.environ.get("S3_BUCKET_LOGS", "")
    app.config["AWS_REGION"] = os.environ.get("AWS_REGION", "us-east-1")
    app.config["LOG_DIR"] = os.environ.get("LOG_DIR", "/var/log/instaretto")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 + 64 * 1024  # +headroom

    configure_logging(app)
    db.init_app(app)

    from app.auth import auth_bp
    from app.posts import posts_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)

    return app
