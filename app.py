from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import os
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "osceai-secret")

def load_case(case_id):
    with open("cases/cases.json", "r") as f:
        cases = json.load(f)
    return cases.get(case_id, None)

@app.route("/")
def home():
    return render_template("index.html")

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

    return jsonify({
        "feedback": feedback,
        "correct_diagnosis": case.get("correct_diagnosis", "")
    })

if __name__ == "__main__":
    app.run(debug=True)