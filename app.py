from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from models import db, User, Result, Feedback
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

    # Auto create admin if not exists
    from models import User
    from werkzeug.security import generate_password_hash
    admin_email = os.getenv("ADMIN_EMAIL", "admin@osceai.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

    existing_admin = User.query.filter_by(
        email=admin_email
    ).first()

    if not existing_admin:
        admin = User(
            full_name="Admin",
            email=admin_email,
            password=generate_password_hash(admin_password),
            university="APU",
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Admin account created: {admin_email}")
    else:
        print("Admin account already exists")
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
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/guest")
def guest():
    logout_user()
    session.clear()
    session["guest"] = True
    session["guest_name"] = "Guest"
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))

# ─────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/simulation")
def simulation():
    case_id = request.args.get("case_id", "")
    case_label = request.args.get("case_label", "")
    return render_template("simulation.html",
                           case_id=case_id,
                           case_label=case_label)

@app.route("/candidate_instructions")
def candidate_instructions():
    case_id = request.args.get("case_id", "abdominal_1")
    case_label = request.args.get("case_label", "")
    return render_template("candidate_instructions.html",
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

@app.route("/mock_exam")
def mock_exam():
    return render_template("mock_exam.html")

@app.route("/mock_results")
def mock_results():
    return render_template("mock_results.html")

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

@app.route("/get_full_case_info")
def get_full_case_info():
    case_id = request.args.get("case_id", "abdominal_1")
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})

    location_map = {
        "abdominal_1": "Emergency Department",
        "abdominal_2": "Surgical Assessment Unit",
        "abdominal_3": "General Practice",
        "chest_1": "Emergency Department",
        "chest_2": "General Practice",
        "chest_3": "Emergency Department",
        "cough_1": "General Practice",
        "cough_2": "General Practice",
        "cough_3": "General Practice"
    }

    complaint_map = {
        "abdominal_1": "Epigastric pain",
        "abdominal_2": "Crampy abdominal pain",
        "abdominal_3": "Burning epigastric pain",
        "chest_1": "Severe central chest pain",
        "chest_2": "Exertional chest pain",
        "chest_3": "Left sided chest pain",
        "cough_1": "Persistent cough",
        "cough_2": "Cough with breathlessness",
        "cough_3": "Productive cough"
    }

    return jsonify({
        "patient_name": case.get("patient_name", ""),
        "age": case.get("age", ""),
        "gender": case.get("gender", ""),
        "location": location_map.get(case_id, "General Practice"),
        "complaint": complaint_map.get(case_id, ""),
        "description": case.get("description", "")
    })

@app.route("/get_candidate_instructions")
def get_candidate_instructions():
    case_id = request.args.get("case_id", "abdominal_1")
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    return jsonify(case.get("candidate_instructions", {}))



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
    pre_checks = data.get("pre_checks", {})
    post_checks = data.get("post_checks", {})
    case = load_case(case_id)
    if not case:
        return jsonify({"error": "Case not found"})
    from services.ai_service import evaluate_checklist
    results = evaluate_checklist(
        conversation,
        case.get("checklist", {}),
        pre_checks,
        post_checks
    )
    return jsonify(results)



@app.route("/get_current_user")
def get_current_user():
    if current_user.is_authenticated:
        return jsonify({
            "name": current_user.full_name,
            "email": current_user.email,
            "university": current_user.university or "—"
        })
    if session.get("guest"):
        return jsonify({
            "name": "Guest",
            "email": "Guest mode",
            "university": "—"
        })
    return jsonify({
        "name": "Guest",
        "email": "",
        "university": "—"
    })
@app.route("/clear_history", methods=["POST"])
def clear_history():
    if current_user.is_authenticated:
        Result.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Not authenticated"})
# ─────────────────────────────────────────
# UPDATE LOGIN — redirect admin to admin panel
# ─────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        flash("Invalid email or password")
    return render_template("login.html")

# ─────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────

@app.route("/admin")
def admin_dashboard():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for("login"))

    users = User.query.filter_by(is_admin=False).all()

    user_data = []
    for user in users:
        results = Result.query.filter_by(user_id=user.id).all()
        total_attempts = len(results)
        avg_score = 0
        if total_attempts > 0:
            avg_score = round(
                sum(r.total_score for r in results) / total_attempts
            )
        user_data.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "university": user.university or "—",
            "total_attempts": total_attempts,
            "avg_score": avg_score,
            "created_at": user.created_at.strftime("%d %b %Y")
        })

    total_users = len(users)
    total_attempts = Result.query.count()

    return render_template("admin.html",
                           user_data=user_data,
                           total_users=total_users,
                           total_attempts=total_attempts)

@app.route("/admin/user/<int:user_id>")
def admin_user_detail(user_id):
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect(url_for("login"))

    user = User.query.get_or_404(user_id)
    results = Result.query.filter_by(
        user_id=user_id
    ).order_by(Result.created_at.desc()).all()

    return render_template("admin_user.html",
                           user=user,
                           results=results)

# ─────────────────────────────────────────
# UPDATE GENERATE FEEDBACK — save full data
# ─────────────────────────────────────────

@app.route("/generate_feedback", methods=["POST"])
def generate_feedback():
    data = request.get_json()
    case_id = data.get("case_id")
    checklist_results = data.get("checklist_results", {})
    viva_scores = data.get("viva_scores", [])
    viva_questions = data.get("viva_questions", [])
    total_score = data.get("total_score", 0)
    total_possible = data.get("total_possible", 0)

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
            global_impression=global_impression,
            checklist_data=json.dumps(checklist_results),
            viva_data=json.dumps({
                "scores": viva_scores,
                "questions": viva_questions,
                "answers": data.get("viva_answers", []),
                "point_results": data.get("viva_point_results", [])
            }),
            ai_feedback=feedback
        )
        db.session.add(result)
        db.session.commit()

    return jsonify({
        "feedback": feedback,
        "correct_diagnosis": case.get("correct_diagnosis", ""),
        "global_impression": global_impression
    })

# ─────────────────────────────────────────
# RESULT DETAIL — for student viewing past results
# ─────────────────────────────────────────

@app.route("/result/<int:result_id>")
def result_detail(result_id):
    result = Result.query.get_or_404(result_id)
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if result.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for("dashboard"))
    return render_template("result_detail.html", result=result)

# ─────────────────────────────────────────
# UPDATE GET USER RESULTS — include result id
# ─────────────────────────────────────────

@app.route("/get_user_results")
def get_user_results():
    if current_user.is_authenticated:
        results = Result.query.filter_by(
            user_id=current_user.id
        ).order_by(Result.created_at.desc()).all()
        return jsonify({
            "results": [{
                "id": r.id,
                "case_id": r.case_id,
                "case_label": r.case_label,
                "checklist_score": r.checklist_score,
                "checklist_possible": r.checklist_possible,
                "viva_score": r.viva_score,
                "viva_possible": r.viva_possible,
                "total_score": r.total_score,
                "total_possible": r.total_possible,
                "global_impression": r.global_impression,
                "created_at": r.created_at.isoformat()
            } for r in results]
        })
    return jsonify({"results": []})
@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    data = request.get_json()
    message = data.get("message", "").strip()
    category = data.get("category", "General")

    if not message:
        return jsonify({"error": "Message is required"})

    name = "Guest"
    email = "—"
    user_id = None

    if current_user.is_authenticated:
        name = current_user.full_name
        email = current_user.email
        user_id = current_user.id

    feedback = Feedback(
        user_id=user_id,
        user_name=name,
        user_email=email,
        message=message,
        category=category
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"success": True})

@app.route("/get_feedback")
def get_feedback():
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({"error": "Unauthorized"})

    feedbacks = Feedback.query.order_by(
        Feedback.created_at.desc()
    ).all()

    return jsonify({
        "feedbacks": [{
            "id": f.id,
            "user_name": f.user_name,
            "user_email": f.user_email,
            "message": f.message,
            "category": f.category,
            "created_at": f.created_at.strftime("%d %b %Y %H:%M")
        } for f in feedbacks]
    })
@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({"error": "Unauthorized"})

    user = User.query.get_or_404(user_id)

    # Delete all results first
    Result.query.filter_by(user_id=user_id).delete()

    # Delete all feedback
    Feedback.query.filter_by(user_id=user_id).delete()

    # Delete user
    db.session.delete(user)
    db.session.commit()

    return jsonify({"success": True})
@app.route("/test_ai")
def test_ai():
    from services.ai_service import call_ai
    result = call_ai([
        {"role": "user", "content": "Say hello in one sentence"}
    ], max_tokens=50, temperature=0.3)
    return jsonify({"result": result})

# ── Update profile ──
@app.route("/update_profile", methods=["POST"])
def update_profile():
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"})

    data = request.get_json()
    full_name = data.get("full_name", "").strip()
    university = data.get("university", "").strip()

    if not full_name:
        return jsonify({"error": "Name cannot be empty"})

    current_user.full_name = full_name
    current_user.university = university
    db.session.commit()

    return jsonify({"success": True})


# ── Change password ──
@app.route("/change_password", methods=["POST"])
def change_password():
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"})

    data = request.get_json()
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not check_password_hash(
        current_user.password, current_password
    ):
        return jsonify({"error": "Current password is incorrect"})

    if len(new_password) < 6:
        return jsonify({
            "error": "New password must be at least 6 characters"
        })

    if new_password != confirm_password:
        return jsonify({"error": "New passwords do not match"})

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"success": True})


# ── Admin update student profile ──
@app.route("/admin/update_user/<int:user_id>", methods=["POST"])
def admin_update_user(user_id):
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({"error": "Unauthorized"})

    data = request.get_json()
    full_name = data.get("full_name", "").strip()
    university = data.get("university", "").strip()

    if not full_name:
        return jsonify({"error": "Name cannot be empty"})

    user = User.query.get_or_404(user_id)
    user.full_name = full_name
    user.university = university
    db.session.commit()

    return jsonify({"success": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
