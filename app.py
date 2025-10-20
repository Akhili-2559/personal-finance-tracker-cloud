from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import traceback
import json

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "akhila_secret_key_123")

# ----------------- Firebase Initialization -----------------
try:
    firebase_config_env = os.getenv("FIREBASE_CONFIG")
    if firebase_config_env:
        # Load Firebase credentials from environment variable (Render)
        cred_dict = json.loads(firebase_config_env)
        cred = credentials.Certificate(cred_dict)
    else:
        # Fallback: local firebase_config.json
        cred_path = os.path.join(os.path.dirname(__file__), "firebase_config.json")
        if not os.path.exists(cred_path):
            raise FileNotFoundError("Place firebase_config.json in project root (service account).")
        cred = credentials.Certificate(cred_path)

    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    raise RuntimeError(f"Firebase initialization failed: {e}")

USERS_COL = "users"
EXPENSES_COL = "expenses"


# ----------------- Helpers -----------------
def get_user_by_username(username):
    """Return dict with user data and id if exists, else None."""
    docs = db.collection(USERS_COL).where("username", "==", username).limit(1).stream()
    for d in docs:
        data = d.to_dict()
        data["id"] = d.id
        return data
    return None


def create_user(username, password):
    """Create user document and return doc id."""
    pw_hash = generate_password_hash(password)
    doc_ref = db.collection(USERS_COL).document()
    doc_ref.set({"username": username, "password": pw_hash, "created_at": firestore.SERVER_TIMESTAMP})
    return doc_ref.id


def add_expense(description, amount, date, category, user_id):
    doc_ref = db.collection(EXPENSES_COL).document()
    doc_ref.set({
        "description": description,
        "amount": float(amount),
        "date": date,
        "category": category,
        "user_id": user_id,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id


def get_expenses(user_id):
    """Fetch expenses for a user without requiring a composite index."""
    docs = db.collection(EXPENSES_COL).where("user_id", "==", user_id).stream()
    items = []
    for d in docs:
        doc = d.to_dict()
        doc["id"] = d.id
        items.append(doc)

    def sort_key(e):
        if "created_at" in e and e["created_at"] is not None:
            return e["created_at"].timestamp()
        try:
            return datetime.strptime(e.get("date", ""), "%Y-%m-%d").timestamp()
        except Exception:
            return 0

    items.sort(key=sort_key, reverse=True)
    return items


def get_expense_by_id(expense_id):
    doc = db.collection(EXPENSES_COL).document(expense_id).get()
    if doc.exists:
        d = doc.to_dict()
        d["id"] = doc.id
        return d
    return None


# ----------------- Routes -----------------
@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Please enter username & password", "error")
            return redirect(url_for("register"))
        if get_user_by_username(username):
            flash("Username already exists", "error")
            return redirect(url_for("register"))
        uid = create_user(username, password)
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if user and check_password_hash(user.get("password", ""), password):
            session["username"] = username
            session["user_id"] = user["id"]
            flash("Logged in successfully", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    try:
        expenses = get_expenses(session["user_id"])
        total = sum(float(e.get("amount", 0)) for e in expenses)
        recent = expenses[:5]
        cat_totals = {}
        for e in expenses:
            cat = e.get("category", "Other")
            cat_totals[cat] = cat_totals.get(cat, 0) + float(e.get("amount", 0))
        return render_template("dashboard.html", total=round(total, 2), recent=recent, cat_totals=cat_totals)
    except Exception:
        traceback.print_exc()
        flash("Error loading dashboard", "error")
        return render_template("dashboard.html", total=0, recent=[], cat_totals={})


@app.route("/add_expense", methods=["GET", "POST"])
def add_expense_route():
    if "username" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        try:
            description = request.form.get("description", "").strip()
            amount = request.form.get("amount", "0")
            date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")

            desc = description.lower()

            food_keywords = [
                "food", "grocery", "restaurant", "biryani", "pizza", "burger", "coffee", "tea", "snacks",
                "bread", "milk", "egg", "fruits", "vegetables", "lunch", "dinner", "breakfast", "juice",
                "icecream", "cake"
            ]
            transport_keywords = [
                "bus", "train", "taxi", "cab", "fuel", "travel", "uber", "ola", "metro", "auto", "petrol",
                "diesel", "parking", "bike", "cycle", "toll", "flight", "ticket", "transport"
            ]
            entertainment_keywords = [
                "movie", "netflix", "ticket", "cinema", "game", "concert", "show", "music", "spotify",
                "youtube", "subscription", "theatre", "play", "amusement", "park", "event", "hobby"
            ]
            housing_keywords = [
                "rent", "house", "electricity", "water", "home", "gas", "maintenance", "internet", "wifi",
                "cleaning", "maid", "repairs", "apartment", "society", "security", "tax", "insurance",
                "furniture", "decor", "utility"
            ]
            health_keywords = [
                "medicine", "doctor", "hospital", "pharmacy", "clinic", "checkup", "consultation",
                "insurance", "dental", "eye", "surgery", "vaccine", "therapist", "treatment", "gym",
                "fitness", "vitamins", "supplements", "diagnosis"
            ]
            other_keywords = [
                "clothes", "books", "stationery", "gift", "toys", "electronics", "mobile", "charger", "bags",
                "shoes", "cosmetics", "accessories", "jewelry", "decorations", "subscription", "pet",
                "gardening", "cleaning", "misc"
            ]

            if any(k in desc for k in food_keywords):
                category = "Food"
            elif any(k in desc for k in transport_keywords):
                category = "Transport"
            elif any(k in desc for k in entertainment_keywords):
                category = "Entertainment"
            elif any(k in desc for k in housing_keywords):
                category = "Housing"
            elif any(k in desc for k in health_keywords):
                category = "Health"
            elif any(k in desc for k in other_keywords):
                category = "Other"
            else:
                category = "Other"

            add_expense(description, amount, date, category, session["user_id"])
            return jsonify({"status": "success", "description": description, "category": category})
        except Exception as e:
            traceback.print_exc()
            return jsonify({"status": "error", "message": str(e)})
    return render_template("add_expense.html")


@app.route("/all_expenses")
def all_expenses():
    if "username" not in session:
        return redirect(url_for("login"))
    expenses = get_expenses(session["user_id"])
    totals = {}
    for e in expenses:
        totals[e.get("category", "Other")] = totals.get(e.get("category", "Other"), 0) + float(e.get("amount", 0))
    return render_template("all_expenses.html", expenses=expenses, totals=totals)


@app.route("/edit_expense/<expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "username" not in session:
        return redirect(url_for("login"))
    doc = get_expense_by_id(expense_id)
    if not doc:
        flash("Expense not found", "error")
        return redirect(url_for("all_expenses"))
    if doc.get("user_id") != session["user_id"]:
        flash("Permission denied", "error")
        return redirect(url_for("all_expenses"))

    if request.method == "POST":
        try:
            description = request.form.get("description", "").strip()
            amount = float(request.form.get("amount", 0))
            date = request.form.get("date")
            category = request.form.get("category", "Other")
            db.collection(EXPENSES_COL).document(expense_id).update({
                "description": description,
                "amount": amount,
                "date": date,
                "category": category
            })
            flash("Expense updated", "success")
            return redirect(url_for("all_expenses"))
        except Exception:
            traceback.print_exc()
            flash("Error updating expense", "error")
            return redirect(url_for("all_expenses"))

    return render_template("edit_expense.html", expense=doc)


@app.route("/delete_expense/<expense_id>", methods=["POST"])
def delete_expense(expense_id):
    if "username" not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    doc = get_expense_by_id(expense_id)
    if not doc:
        return jsonify({"status": "error", "message": "Not found"}), 404
    if doc.get("user_id") != session["user_id"]:
        return jsonify({"status": "error", "message": "Permission denied"}), 403
    try:
        db.collection(EXPENSES_COL).document(expense_id).delete()
        return jsonify({"status": "success", "message": "Deleted"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/summary")
def summary():
    if "username" not in session:
        return redirect(url_for("login"))
    expenses = get_expenses(session["user_id"])
    totals = {}
    total_amount = 0
    for e in expenses:
        amt = float(e.get("amount", 0))
        cat = e.get("category", "Other")
        totals[cat] = totals.get(cat, 0) + amt
        total_amount += amt
    labels = list(totals.keys())
    values = [round(v, 2) for v in totals.values()]
    return render_template("summary.html", labels=labels, values=values)


@app.route('/recommendations')
def recommendations():
    if 'username' not in session:
        return redirect(url_for('login'))

    expenses = get_expenses(session['user_id'])
    category_sum = {}
    total = 0
    for e in expenses:
        amt = float(e.get('amount', 0))
        total += amt
        cat = e.get('category', 'Other')
        category_sum[cat] = category_sum.get(cat, 0) + amt

    percentages = {k:(v/total*100) for k,v in category_sum.items()} if total>0 else {}

    category_tips = {
        "Food": "Try cooking at home, meal prep, or reduce takeout orders.",
        "Transport": "Use public transport, carpool, or walk/cycle for short distances.",
        "Entertainment": "Switch to free/low-cost activities or reduce streaming subscriptions.",
        "Housing": "Monitor utility usage, save energy, and avoid unnecessary expenses.",
        "Health": "Look for affordable healthcare options, generic medicines, and preventive care.",
        "Other": "Track miscellaneous spending and prioritize essentials over luxuries."
    }

    messages = {}
    for cat, perc in percentages.items():
        if perc > 50:
            messages[cat] = f"💡 Tip: {category_tips.get(cat, 'Reduce unnecessary expenses.')}"
        else:
            messages[cat] = "💡 Spending is under control ✅ Don't worry."

    sorted_percentages = dict(sorted(percentages.items(), key=lambda x: x[1], reverse=True))
    sorted_messages = {k: messages[k] for k in sorted_percentages.keys()}

    return render_template('recommendations.html', percentages=sorted_percentages, messages=sorted_messages)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
