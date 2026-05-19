from dotenv import load_dotenv
import os
import json

load_dotenv()


def load_case(case_id):
    with open("cases/cases.json", "r") as f:
        cases = json.load(f)
    return cases.get(case_id, None)


def get_symptom_image(response_text):
    response_lower = response_text.lower()

    if any(word in response_lower for word in [
        "stomach", "abdomen", "abdominal", "belly", "tummy",
        "epigastric", "bowel", "intestine"
    ]):
        return "stomach.png"

    if any(word in response_lower for word in [
        "chest", "heart", "cardiac", "aorta", "angina"
    ]):
        return "chest.png"

    if any(word in response_lower for word in [
        "cough", "lung", "breathing", "breath", "respiratory",
        "wheeze", "sputum", "phlegm"
    ]):
        return "lungs.png"

    return None


def get_groq_client():
    from groq import Groq
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_patient_response(user_message, case_id):
    case = load_case(case_id)

    if not case:
        return {
            "response": "Sorry, case not found.",
            "image": None
        }

    system_prompt = f"""You are roleplaying as a real patient in a medical OSCE exam. Stay in character at all times.

IDENTITY:
Name: {case['patient_name']}
Age: {case['age']}
Where you are: {case['description']}
Why you came: {case['symptoms'].split('.')[0] if case['symptoms'] else 'I am not feeling well'}

INFORMATION YOU KNOW - only reveal when directly asked:
- Full symptoms: {case['symptoms']}
- Things you do NOT have: {case.get('negative_features', 'None')}
- Past medical history: {case.get('past_medical_history', 'Nothing significant')}
- Medications: {case.get('drug_history', 'None')}
- Family history: {case.get('family_history', 'Nothing significant')}
- Social history: {case.get('social_history', 'Nothing significant')}
- Your ideas about what is wrong: {case.get('ice', {}).get('ideas', 'I am not sure')}
- Your concerns: {case.get('ice', {}).get('concerns', 'I just want to feel better')}
- Your expectations: {case.get('ice', {}).get('expectations', 'I hope the doctor can help')}

STRICT RULES:
1. Answer only what was directly asked.
2. Never volunteer extra information.
3. If asked an opening question, give only the main complaint and duration.
4. Never mention radiation unless asked if the pain spreads.
5. Never mention severity unless asked how bad it is.
6. Never mention associated symptoms unless directly asked.
7. Never mention past history, medications, family history, or social history unless directly asked.
8. Never reveal the diagnosis.
9. If you already answered something, briefly confirm instead of repeating the full detail.
10. Keep responses to 1-2 short sentences.
11. If asked something you do not know, say "I am not sure doctor".
12. Respond naturally like a real patient, not like a textbook.

Correct behaviour:
Student: "What brings you in today?"
You: "I have been having really bad chest pain since this morning."

Wrong behaviour:
Student: "What brings you in today?"
You: "I have chest pain that started this morning, it radiates to my left arm, I feel nauseous, I have hypertension and I take amlodipine."

Remember: answer one question at a time."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=80,
        temperature=0.3,
    )

    patient_response = response.choices[0].message.content
    image = get_symptom_image(patient_response)

    return {
        "response": patient_response,
        "image": image
    }


def is_pre_post_item_achieved(item_text, pre_checks, post_checks):
    text = item_text.lower()

    if (
        "washes hands" in text and
        ("ppe" in text or "dons ppe" in text) and
        pre_checks.get("washed_hands") and
        pre_checks.get("donned_ppe")
    ):
        return True

    if (
        "disposes ppe" in text and
        "washes hands" in text and
        post_checks.get("disposed_ppe") and
        post_checks.get("washed_hands_after")
    ):
        return True

    if "summarises" in text and post_checks.get("summarised"):
        return True

    if "thanks" in text and post_checks.get("thanked_patient"):
        return True

    return False


def evaluate_checklist(
    conversation_history,
    checklist,
    pre_checks=None,
    post_checks=None
):
    results = {}
    total_possible = 0
    total_achieved = 0

    pre_checks = pre_checks or {}
    post_checks = post_checks or {}

    full_conversation = " ".join([
        msg.get("content", "").lower()
        for msg in conversation_history
        if msg.get("role") == "user"
    ])

    for section, items in checklist.items():
        section_results = []
        section_achieved = 0
        section_possible = 0

        for item in items:
            keywords = [kw.lower() for kw in item["keywords"]]
            achieved = any(kw in full_conversation for kw in keywords)

            if is_pre_post_item_achieved(
                item["item"], pre_checks, post_checks
            ):
                achieved = True

            section_results.append({
                "item": item["item"],
                "achieved": achieved,
                "mark": 1 if achieved else 0
            })

            total_possible += 1
            section_possible += 1

            if achieved:
                total_achieved += 1
                section_achieved += 1

        results[section] = {
            "items": section_results,
            "section_achieved": section_achieved,
            "section_possible": section_possible
        }

    return {
        "sections": results,
        "total_achieved": total_achieved,
        "total_possible": total_possible
    }


def evaluate_viva_answer(user_answer, viva_question):
    answer_lower = user_answer.lower()
    marks_achieved = 0
    point_results = []
    required_missed = False

    for point in viva_question["marking_points"]:
        keywords = [kw.lower() for kw in point["keywords"]]
        achieved = any(kw in answer_lower for kw in keywords)

        if point.get("required") and not achieved:
            required_missed = True

        point_results.append({
            "point": point["point"],
            "achieved": achieved,
            "mark": 1 if achieved else 0,
            "required": point.get("required", False)
        })

        if achieved:
            marks_achieved += 1

    if required_missed:
        marks_achieved = 0
        for result in point_results:
            result["achieved"] = False
            result["mark"] = 0

    return {
        "marks_achieved": marks_achieved,
        "max_marks": viva_question["max_marks"],
        "point_results": point_results,
        "required_missed": required_missed
    }


def generate_overall_feedback(
    checklist_results,
    viva_scores,
    viva_questions,
    case_id
):
    case = load_case(case_id)

    if not case:
        return "Unable to generate feedback."

    checklist_total = checklist_results.get("total_achieved", 0)
    checklist_possible = checklist_results.get("total_possible", 0)

    viva_total = sum(viva_scores)
    viva_possible = sum(q["max_marks"] for q in viva_questions)

    overall_total = checklist_total + viva_total
    overall_possible = checklist_possible + viva_possible

    missed_items = []

    for section, data in checklist_results.get("sections", {}).items():
        for item in data.get("items", []):
            if not item.get("achieved"):
                missed_items.append(item.get("item", ""))

    missed_str = ", ".join(missed_items[:5]) if missed_items else "None"

    prompt = f"""You are an experienced OSCE examiner giving feedback to a medical student.

Case: {case['description']}
Correct diagnosis: {case['correct_diagnosis']}

Student performance:
- Checklist score: {checklist_total} out of {checklist_possible}
- Viva score: {viva_total} out of {viva_possible}
- Overall score: {overall_total} out of {overall_possible}

Key checklist items the student missed:
{missed_str}

Please provide:
1. Two sentences of positive feedback on what they did well.
2. Two sentences on the main areas they need to improve.
3. One sentence on the most important clinical point they should remember.

Keep the feedback encouraging, specific, and clinically relevant.
Total response should be 5-6 sentences maximum."""

    response = get_groq_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.4,
    )

    return response.choices[0].message.content