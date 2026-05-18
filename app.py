from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from models import db, User, Result
import os
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "osceai-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///osceai.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

def load_case(case_id):
    with open("cases/cases.json", "r") as f:
        cases = json.load(f)
    return cases.get(case_id, None)

# ─────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────

@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("simulation"))
        flash("Invalid email or password")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        university = request.form.get("university")
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please login.")
            return redirect(url_for("login"))
        hashed_password = generate_password_hash(password)
        new_user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            university=university
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("simulation"))
    return render_template("register.html")

@app.route("/guest")
def guest():
    session["guest"] = True
    session["guest_name"] = "Guest"
    return redirect(url_for("simulation"))

@app.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))

# ─────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────

@app.route("/simulation")
def simulation():
    case_id = request.args.get("case_id", "")
    case_label = request.args.get("case_label", "")
    return render_template("simulation.html",
                           case_id=case_id,
                           case_label=case_label)

@app.route("/pre_check")
def pre_check():
    case_id = request.args.get("case_id", "abdominal_1")
    case_label = request.args.get("case_label", "")
    return render_template("pre_check.html",
                           case_id=case_id,
                           case_label=case_label)

@app.route("/post_check")
def post_check():
    case_id = request.args.get("case_id", "abdominal_1")
    return render_template("post_check.html", case_id=case_id)

@app.route("/examiner")
def examiner():
    case_id = request.args.get("case_id", "abdominal_1")
    return render_template("examiner.html", case_id=case_id)

@app.route("/feedback")
def feedback():
    case_id = request.args.get("case_id", "abdominal_1")
    return render_template("feedback.html", case_id=case_id)

# ─────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    case_id = data.get("case_id", "abdominal_1")
    from services.ai_service import get_patient_response
    response = get_patient_response(user_message, case_id)
    return jsonify(response)

@app.route("/get_questions")
def get_questions():
    case_id = request.args.get("case_id", "abdominal_1")
    case = load_case(case_id)
    if not case:
        return jsonify({"questions": []})
    return jsonify({"questions": case.get("viva_questions", [])})

@app.route("/get_case_info")
def get_case_info():
    case_id = request.args.get("case_id", "abdominal_1")
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    return jsonify({
        "age": case.get("age", 30),
        "gender": case.get("gender", "female"),
        "patient_name": case.get("patient_name", "Patient")
    })

@app.route("/evaluate_viva", methods=["POST"])
def evaluate_viva_route():
    data = request.get_json()
    case_id = data.get("case_id")
    question_index = data.get("question_index", 0)
    user_answer = data.get("answer", "")
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    viva_question = case["viva_questions"][question_index]
    from services.ai_service import evaluate_viva_answer
    results = evaluate_viva_answer(user_answer, viva_question)
    return jsonify(results)

@app.route("/evaluate_checklist", methods=["POST"])
def evaluate_checklist_route():
    data = request.get_json()
    case_id = data.get("case_id")
    conversation = data.get("conversation", [])
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    from services.ai_service import evaluate_checklist
    results = evaluate_checklist(conversation, case.get("checklist", {}))
    return jsonify(results)

@app.route("/generate_feedback", methods=["POST"])
def generate_feedback():
    data = request.get_json()
    case_id = data.get("case_id")
    checklist_results = data.get("checklist_results", {})
    viva_scores = data.get("viva_scores", [])
    viva_questions = data.get("viva_questions", [])
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    from services.ai_service import generate_overall_feedback
    feedback = generate_overall_feedback(
        checklist_results,
        viva_scores,
        viva_questions,
        case_id
    )

    total_score = data.get("total_score", 0)
    total_possible = data.get("total_possible", 0)
    checklist_score = checklist_results.get("total_achieved", 0)
    checklist_possible = checklist_results.get("total_possible", 0)
    viva_total = sum(viva_scores)
    viva_possible = sum(q["max_marks"] for q in viva_questions)

    pct = (total_score / total_possible * 100) if total_possible > 0 else 0
    if pct >= 80:
        global_impression = "Excellent"
    elif pct >= 65:
        global_impression = "Pass"
    elif pct >= 50:
        global_impression = "Borderline"
    else:
        global_impression = "Fail"

    if current_user.is_authenticated:
        result = Result(
            user_id=current_user.id,
            case_id=case_id,
            case_label=case.get("description", case_id),
            checklist_score=checklist_score,
            checklist_possible=checklist_possible,
            viva_score=viva_total,
            viva_possible=viva_possible,
            total_score=total_score,
            total_possible=total_possible,
            global_impression=global_impression
        )
        db.session.add(result)
        db.session.commit()

    return jsonify({
        "feedback": feedback,
        "correct_diagnosis": case.get("correct_diagnosis", ""),
        "global_impression": global_impression
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)