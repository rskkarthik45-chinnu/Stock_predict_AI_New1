import os
import re
from datetime import datetime, timezone
from functools import wraps
from getpass import getpass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from sqlalchemy import inspect

from utils.prediction import predict_stock_price
from utils.data_processing import download_stock_data

from config import Config


# ==========================================
# APPLICATION SETUP
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

app.config.from_object(Config)

os.makedirs(
    os.path.join(BASE_DIR, "database"),
    exist_ok=True
)

db = SQLAlchemy(app)

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"

login_manager.login_message_category = "error"


# ==========================================
# DATABASE MODELS
# ==========================================

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="user",
        nullable=False
    )

    is_blocked = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class Prediction(db.Model):

    __tablename__ = "predictions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    symbol = db.Column(
        db.String(20),
        nullable=False
    )

    current_price = db.Column(
        db.Float,
        nullable=False
    )

    predicted_price = db.Column(
        db.Float,
        nullable=False
    )

    prediction_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="predictions"
    )


# ==========================================
# DATABASE MIGRATION
# ==========================================

def migrate_database():

    inspector = inspect(db.engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    with db.engine.begin() as connection:

        if "role" not in columns:

            connection.exec_driver_sql(
                """
                ALTER TABLE users
                ADD COLUMN role VARCHAR(20)
                NOT NULL DEFAULT 'user'
                """
            )

        if "is_blocked" not in columns:

            connection.exec_driver_sql(
                """
                ALTER TABLE users
                ADD COLUMN is_blocked BOOLEAN
                NOT NULL DEFAULT 0
                """
            )


with app.app_context():

    db.create_all()

    migrate_database()


# ==========================================
# LOGIN MANAGER
# ==========================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (ValueError, TypeError):

        return None


# ==========================================
# ACCESS CONTROL
# ==========================================

def admin_required(func):

    @wraps(func)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.is_blocked:

            logout_user()

            flash(
                "Your account has been blocked.",
                "error"
            )

            return redirect(url_for("login"))

        if current_user.role != "admin":

            flash(
                "Admin access required.",
                "error"
            )

            return redirect(url_for("dashboard"))

        return func(*args, **kwargs)

    return decorated_function


@app.before_request
def check_blocked_account():

    if (
        current_user.is_authenticated
        and current_user.is_blocked
    ):

        logout_user()

        flash(
            "Your account has been blocked.",
            "error"
        )

        return redirect(url_for("login"))


# ==========================================
# ADMIN ACCOUNT CREATION COMMAND
# ==========================================

@app.cli.command("create-admin")
def create_admin():

    email = input("Enter admin email: ").strip().lower()

    password = getpass("Enter admin password: ")

    confirm = getpass("Confirm admin password: ")

    if not email or not password:

        print("Email and password are required.")

        return

    if len(password) < 8:

        print("Password must contain at least 8 characters.")

        return

    if password != confirm:

        print("Passwords do not match.")

        return

    admin = db.session.scalar(
        db.select(User).where(User.email == email)
    )

    if admin is None:

        admin = User(
            name="Administrator",
            email=email,
            password_hash=generate_password_hash(password),
            role="admin",
            is_blocked=False
        )

        db.session.add(admin)

    else:

        admin.password_hash = generate_password_hash(password)

        admin.role = "admin"

        admin.is_blocked = False

    db.session.commit()

    print("Admin account created or updated successfully.")


# ==========================================
# VALID STOCK SYMBOL
# ==========================================

def valid_symbol(symbol):

    if not symbol:

        return False

    return bool(
        re.fullmatch(
            r"[A-Za-z0-9.^_-]{1,20}",
            symbol.strip()
        )
    )


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def index():

    if current_user.is_authenticated:

        if current_user.role == "admin":

            return redirect(
                url_for("admin_dashboard")
            )

        return redirect(
            url_for("dashboard")
        )

    return redirect(url_for("login"))


# ==========================================
# SIGNUP
# ==========================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if current_user.is_authenticated:

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not name or not email or not password:

            flash(
                "Please fill all fields.",
                "error"
            )

            return render_template("signup.html")

        if len(name) > 100 or len(email) > 150:

            flash(
                "Name or email is too long.",
                "error"
            )

            return render_template("signup.html")

        if len(password) < 8:

            flash(
                "Password must contain at least 8 characters.",
                "error"
            )

            return render_template("signup.html")

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template("signup.html")

        existing_user = db.session.scalar(
            db.select(User).where(
                User.email == email
            )
        )

        if existing_user:

            flash(
                "Email already registered.",
                "error"
            )

            return render_template("signup.html")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
            is_blocked=False
        )

        try:

            db.session.add(user)

            db.session.commit()

            flash(
                "Account created successfully.",
                "success"
            )

            return redirect(url_for("login"))

        except Exception:

            db.session.rollback()

            app.logger.exception(
                "Registration failed."
            )

            flash(
                "Registration failed.",
                "error"
            )

    return render_template("signup.html")


# ==========================================
# USER LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:

        if current_user.role == "admin":

            return redirect(
                url_for("admin_dashboard")
            )

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        user = db.session.scalar(
            db.select(User).where(
                User.email == email
            )
        )

        if user and check_password_hash(
            user.password_hash,
            password
        ):

            if user.is_blocked:

                flash(
                    "Your account has been blocked.",
                    "error"
                )

                return render_template("login.html")

            login_user(user)

            if user.role == "admin":

                return redirect(
                    url_for("admin_dashboard")
                )

            flash(
                "Login successful!",
                "success"
            )

            return redirect(url_for("dashboard"))

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template("login.html")


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if current_user.is_authenticated:

        if current_user.role == "admin":

            return redirect(
                url_for("admin_dashboard")
            )

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        admin = db.session.scalar(
            db.select(User).where(
                User.email == email
            )
        )

        if (
            admin
            and admin.role == "admin"
            and not admin.is_blocked
            and check_password_hash(
                admin.password_hash,
                password
            )
        ):

            login_user(admin)

            flash(
                "Admin login successful!",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid admin credentials.",
            "error"
        )

    return render_template("admin_login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect(url_for("login"))


# ==========================================
# USER DASHBOARD
# ==========================================

@app.route("/dashboard")
@login_required
def dashboard():

    if current_user.role == "admin":

        return redirect(
            url_for("admin_dashboard")
        )

    recent_predictions = db.session.scalars(

        db.select(Prediction)
        .where(
            Prediction.user_id == current_user.id
        )
        .order_by(
            Prediction.prediction_date.desc()
        )
        .limit(5)

    ).all()

    return render_template(
        "dashboard.html",
        recent_predictions=recent_predictions
    )


# ==========================================
# STOCK PREDICTION
# ==========================================

@app.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():

    if current_user.role == "admin":

        return redirect(
            url_for("admin_dashboard")
        )

    result = None

    if request.method == "POST":

        symbol = request.form.get(
            "symbol", ""
        ).strip().upper()

        period = request.form.get(
            "period", "1y"
        )

        days_text = request.form.get(
            "days", "5"
        )

        try:

            if not valid_symbol(symbol):

                raise ValueError(
                    "Invalid stock symbol."
                )

            if period not in {
                "6mo", "1y", "2y", "5y"
            }:

                raise ValueError(
                    "Invalid historical period."
                )

            if days_text not in {
                "1", "5", "10", "20"
            }:

                raise ValueError(
                    "Invalid prediction days."
                )

            days = int(days_text)

            result = predict_stock_price(
                symbol=symbol,
                period=period,
                days=days
            )

            record = Prediction(
                user_id=current_user.id,
                symbol=result["symbol"],
                current_price=result["current_price"],
                predicted_price=result["predicted_price"]
            )

            db.session.add(record)

            db.session.commit()

            flash(
                "Prediction saved successfully!",
                "success"
            )

        except Exception as error:

            db.session.rollback()

            app.logger.exception(
                "Prediction failed."
            )

            flash(
                f"Prediction failed: {error}",
                "error"
            )

    return render_template(
        "prediction.html",
        result=result
    )


# ==========================================
# USER PREDICTION HISTORY
# ==========================================

@app.route("/history")
@login_required
def history():

    if current_user.role == "admin":

        return redirect(
            url_for("admin_prediction_history")
        )

    predictions = db.session.scalars(

        db.select(Prediction)
        .where(
            Prediction.user_id == current_user.id
        )
        .order_by(
            Prediction.prediction_date.desc()
        )

    ).all()

    return render_template(
        "history.html",
        predictions=predictions
    )


# ==========================================
# STOCK COMPARISON
# ==========================================

@app.route("/comparison", methods=["GET", "POST"])
@login_required
def comparison():

    if current_user.role == "admin":

        return redirect(
            url_for("admin_dashboard")
        )

    comparison_result = None

    if request.method == "POST":

        symbol1 = request.form.get(
            "symbol1", ""
        ).strip().upper()

        symbol2 = request.form.get(
            "symbol2", ""
        ).strip().upper()

        period = request.form.get(
            "period", "1y"
        )

        try:

            if (
                not valid_symbol(symbol1)
                or not valid_symbol(symbol2)
            ):

                raise ValueError(
                    "Enter valid stock symbols."
                )

            if symbol1 == symbol2:

                raise ValueError(
                    "Enter two different symbols."
                )

            if period not in {
                "6mo", "1y", "2y", "5y"
            }:

                raise ValueError(
                    "Invalid period."
                )

            data1 = download_stock_data(
                symbol1,
                period
            )

            data2 = download_stock_data(
                symbol2,
                period
            )

            if data1.empty or data2.empty:

                raise ValueError(
                    "No stock data available."
                )

            price1 = float(
                data1["Close"].iloc[-1]
            )

            price2 = float(
                data2["Close"].iloc[-1]
            )

            series1 = data1.set_index(
                "Date"
            )["Close"]

            series2 = data2.set_index(
                "Date"
            )["Close"]

            normalized1 = (
                series1 / series1.iloc[0]
            ) * 100

            normalized2 = (
                series2 / series2.iloc[0]
            ) * 100

            plt.figure(figsize=(10, 5))

            plt.plot(
                normalized1.index,
                normalized1.values,
                label=symbol1
            )

            plt.plot(
                normalized2.index,
                normalized2.values,
                label=symbol2
            )

            plt.title(
                "Stock Performance Comparison"
            )

            plt.xlabel("Date")

            plt.ylabel(
                "Normalized Price"
            )

            plt.legend()

            plt.grid(True, alpha=0.3)

            plt.tight_layout()

            image_folder = os.path.join(
                BASE_DIR,
                "static",
                "images"
            )

            os.makedirs(
                image_folder,
                exist_ok=True
            )

            filename = (
                f"comparison_{current_user.id}.png"
            )

            image_path = os.path.join(
                image_folder,
                filename
            )

            plt.savefig(
                image_path,
                dpi=120
            )

            plt.close()

            comparison_result = {

                "symbol1": symbol1,

                "symbol2": symbol2,

                "price1": round(price1, 2),

                "price2": round(price2, 2),

                "chart": f"images/{filename}"

            }

        except Exception as error:

            plt.close()

            app.logger.exception(
                "Comparison failed."
            )

            flash(
                f"Comparison failed: {error}",
                "error"
            )

    return render_template(
        "comparison.html",
        comparison_result=comparison_result
    )


# ==========================================
# USER PROFILE
# ==========================================

@app.route("/profile")
@login_required
def profile():

    if current_user.role == "admin":

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template("profile.html")


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    total_users = db.session.scalar(

        db.select(
            db.func.count(User.id)
        ).where(
            User.role == "user"
        )

    ) or 0

    blocked_users = db.session.scalar(

        db.select(
            db.func.count(User.id)
        ).where(
            User.role == "user",
            User.is_blocked.is_(True)
        )

    ) or 0

    active_users = total_users - blocked_users

    total_predictions = db.session.scalar(

        db.select(
            db.func.count(Prediction.id)
        )

    ) or 0

    recent_users = db.session.scalars(

        db.select(User)
        .where(
            User.role == "user"
        )
        .order_by(
            User.created_at.desc()
        )
        .limit(5)

    ).all()

    return render_template(

        "admin_dashboard.html",

        total_users=total_users,

        active_users=active_users,

        blocked_users=blocked_users,

        total_predictions=total_predictions,

        recent_users=recent_users

    )


# ==========================================
# MANAGE USERS
# ==========================================

@app.route("/admin/users")
@admin_required
def manage_users():

    users = db.session.scalars(

        db.select(User)
        .where(
            User.role == "user"
        )
        .order_by(
            User.created_at.desc()
        )

    ).all()

    return render_template(
        "manage_users.html",
        users=users
    )


# ==========================================
# USER DETAILS
# ==========================================

@app.route("/admin/users/<int:user_id>")
@admin_required
def user_details(user_id):

    user = db.session.get(
        User,
        user_id
    )

    if not user or user.role != "user":

        flash(
            "User not found.",
            "error"
        )

        return redirect(
            url_for("manage_users")
        )

    predictions = db.session.scalars(

        db.select(Prediction)
        .where(
            Prediction.user_id == user.id
        )
        .order_by(
            Prediction.prediction_date.desc()
        )

    ).all()

    return render_template(

        "user_details.html",

        user=user,

        predictions=predictions

    )


# ==========================================
# BLOCK / UNBLOCK USERS
# ==========================================

@app.route(
    "/admin/users/<int:user_id>/toggle",
    methods=["POST"]
)
@admin_required
def toggle_user(user_id):

    user = db.session.get(
        User,
        user_id
    )

    if not user or user.role != "user":

        flash(
            "User not found.",
            "error"
        )

        return redirect(
            url_for("manage_users")
        )

    user.is_blocked = not user.is_blocked

    db.session.commit()

    flash(
        "User status updated successfully.",
        "success"
    )

    return redirect(
        url_for("manage_users")
    )


# ==========================================
# DELETE USERS
# ==========================================

@app.route(
    "/admin/users/<int:user_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_user(user_id):

    user = db.session.get(User, user_id)

    if not user or user.role != "user":

        flash("User not found.", "error")

        return redirect(url_for("manage_users"))

    try:

        # Delete user's prediction history
        db.session.execute(
            db.delete(Prediction).where(
                Prediction.user_id == user.id
            )
        )

        # Delete user account
        db.session.delete(user)

        db.session.commit()

        flash(
            "User deleted successfully.",
            "success"
        )

    except Exception:

        db.session.rollback()

        app.logger.exception("User deletion failed.")

        flash(
            "Unable to delete user.",
            "error"
        )

    return redirect(url_for("manage_users"))

# ==========================================
# ADMIN PREDICTION HISTORY
# ==========================================

@app.route("/admin/predictions")
@admin_required
def admin_prediction_history():

    predictions = db.session.scalars(

        db.select(Prediction)
        .order_by(
            Prediction.prediction_date.desc()
        )

    ).all()

    return render_template(
        "prediction_history.html",
        predictions=predictions
    )


# ==========================================
# ERROR HANDLER
# ==========================================

@app.errorhandler(404)
def page_not_found(error):

    return "Page not found.", 404


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)