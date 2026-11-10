import os
import re
from datetime import datetime, timezone

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_sqlalchemy import SQLAlchemy
from utils.prediction import predict_stock_price
from utils.data_processing import download_stock_data
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config


# ==========================================
# APPLICATION SETUP
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "database"),
    exist_ok=True,
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

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    symbol = db.Column(db.String(20), nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    predicted_price = db.Column(db.Float, nullable=False)
    prediction_date = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ==========================================
# LOGIN MANAGER
# ==========================================

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ==========================================
# HOME PAGE
# ==========================================

def valid_symbol(symbol):
    if not symbol:
        return False

    return bool(
        re.fullmatch(r"[A-Za-z0-9.^_-]{1,20}", symbol.strip())
    )
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ==========================================
# SIGNUP
# ==========================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("signup.html")

        if len(name) > 100 or len(email) > 150:
            flash("Name or email is too long.", "error")
            return render_template("signup.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        existing_user = db.session.scalar(
            db.select(User).where(User.email == email)
        )

        if existing_user:
            flash("This email is already registered.", "error")
            return render_template("signup.html")

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
        )

        try:
            db.session.add(user)
            db.session.commit()

            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))

        except Exception:
            db.session.rollback()
            app.logger.exception("User registration failed.")
            flash("Registration failed. Please try again.", "error")

    return render_template("signup.html")


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.scalar(
            db.select(User).where(User.email == email)
        )

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()
    flash("You have logged out successfully.", "success")

    return redirect(url_for("login"))


# ==========================================
# DASHBOARD
# ==========================================

@app.route("/dashboard")
@login_required
def dashboard():

    recent_predictions = db.session.scalars(
        db.select(Prediction)
        .where(Prediction.user_id == current_user.id)
        .order_by(Prediction.prediction_date.desc())
        .limit(5)
    ).all()

    return render_template(
        "dashboard.html",
        recent_predictions=recent_predictions,
    )


# ==========================================
# PREDICTION PAGE
# ==========================================

@app.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    result = None

    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip().upper()
        period = request.form.get("period", "1y")
        days_text = request.form.get("days", "5")

        try:
            if not valid_symbol(symbol):
                raise ValueError("Please enter a valid stock symbol.")

            if period not in {"6mo", "1y", "2y", "5y"}:
                raise ValueError("Please select a valid historical period.")

            if days_text not in {"1", "5", "10", "20"}:
                raise ValueError("Please select a valid prediction horizon.")

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

            flash("Prediction generated and saved successfully!", "success")

        except Exception:
            db.session.rollback()
            flash(
    f"Prediction failed: {__import__('traceback').format_exc().splitlines()[-1]}",
    "error"
)
            flash(
                "Prediction failed. Check your internet connection and terminal for errors.",
                "error"
            )

    return render_template("prediction.html", result=result)


# ==========================================
# PREDICTION HISTORY
# ==========================================

@app.route("/history")
@login_required
def history():

    predictions = db.session.scalars(
        db.select(Prediction)
        .where(Prediction.user_id == current_user.id)
        .order_by(Prediction.prediction_date.desc())
    ).all()

    return render_template(
        "history.html",
        predictions=predictions,
    )


# ==========================================
# STOCK COMPARISON
# ==========================================

@app.route("/comparison", methods=["GET", "POST"])
@login_required
def comparison():

    comparison_result = None

    if request.method == "POST":

        symbol1 = request.form.get("symbol1", "").strip().upper()
        symbol2 = request.form.get("symbol2", "").strip().upper()
        period = request.form.get("period", "1y")

        try:
            # Validate stock symbols
            if not symbol1 or not symbol2:
                raise ValueError("Please enter both stock symbols.")

            if not valid_symbol(symbol1) or not valid_symbol(symbol2):
                raise ValueError("Please enter valid stock symbols.")

            if symbol1 == symbol2:
                raise ValueError("Please enter two different stock symbols.")

            # Validate period
            allowed_periods = {"6mo", "1y", "2y", "5y"}

            if period not in allowed_periods:
                raise ValueError("Please select a valid comparison period.")

            # Download historical stock data
            data1 = download_stock_data(symbol1, period)
            data2 = download_stock_data(symbol2, period)

            if data1.empty or data2.empty:
                raise ValueError("No stock data available.")

            # Get latest closing prices
            price1 = float(data1["Close"].iloc[-1])
            price2 = float(data2["Close"].iloc[-1])

            # Create comparison chart
            series1 = data1.set_index("Date")["Close"]
            series2 = data2.set_index("Date")["Close"]

            # Normalize prices to compare performance
            normalized1 = (series1 / series1.iloc[0]) * 100
            normalized2 = (series2 / series2.iloc[0]) * 100

            import matplotlib.pyplot as plt

            plt.figure(figsize=(10, 5))

            plt.plot(
                normalized1.index,
                normalized1.values,
                label=symbol1,
                linewidth=2
            )

            plt.plot(
                normalized2.index,
                normalized2.values,
                label=symbol2,
                linewidth=2
            )

            plt.title("Stock Performance Comparison")
            plt.xlabel("Date")
            plt.ylabel("Normalized Price (Starting Value = 100)")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.tight_layout()

            # Save chart
            image_folder = os.path.join(
                BASE_DIR, "static", "images"
            )
            os.makedirs(image_folder, exist_ok=True)

            filename = f"comparison_{current_user.id}.png"
            image_path = os.path.join(image_folder, filename)

            plt.savefig(image_path, dpi=120)
            plt.close()

            # Send results to HTML page
            comparison_result = {
                "symbol1": symbol1,
                "symbol2": symbol2,
                "price1": round(price1, 2),
                "price2": round(price2, 2),
                "chart": f"images/{filename}"
            }

        except Exception as error:
            app.logger.exception("Stock comparison failed.")
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

    return render_template("profile.html")


# ==========================================
# ERROR HANDLERS
# ==========================================

@app.errorhandler(404)
def page_not_found(error):
    return "Page not found.", 404


# ==========================================
# CREATE DATABASE TABLES
# ==========================================

with app.app_context():
    db.create_all()


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)