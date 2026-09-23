from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("signup.html")

        user = User(
            email=email,
            password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current_app.logger.info("signup_failed reason=email_taken email=%s", email)
            flash("That email is already registered.")
            return render_template("signup.html")

        current_app.logger.info("signup_success user_id=%s email=%s", user.id, email)
        session.clear()
        session["user_id"] = user.id
        return redirect(url_for("posts.feed"))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.query(User).filter_by(email=email).first()
        if user is None or not check_password_hash(user.password_hash, password):
            current_app.logger.info("login_failed email=%s", email)
            flash("Invalid email or password.")
            return render_template("login.html")

        current_app.logger.info("login_success user_id=%s email=%s", user.id, email)
        session.clear()
        session["user_id"] = user.id
        return redirect(url_for("posts.feed"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    if g.user is not None:
        current_app.logger.info("logout user_id=%s", g.user.id)
    session.clear()
    return redirect(url_for("auth.login"))
