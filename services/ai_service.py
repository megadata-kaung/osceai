from groq import Groq
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def load_case(case_id):
    with open("cases/cases.json", "r") as f:
        cases = json.load(f)
    return cases.get(case_id, None)

def get_symptom_image(response_text):
    response_lower = response_text.lower()
    if any(word in response_lower for word in ["stomach", "abdomen", "abdominal", "belly", "tummy", "epigastric", "bowel", "intestine"]):
        return "stomach.png"
    elif any(word in response_lower for word in ["chest", "heart", "cardiac", "aorta", "angina"]):
        return "chest.png"
    elif any(word in response_lower for word in ["cough", "lung", "breathing", "breath", "respiratory", "wheeze", "sputum", "phlegm"]):
        return "lungs.png"
    else:
        return None

def get_patient_response(user_message, case_id):
    case = load_case(case_id)

    if not case:
        return {
            "response": "Sorry, case not found.",
            "image": None
        }

    system_prompt = f"""You are a virtual patient in a medical simulation for OSCE training.
    Your name is {case['patient_name']}, aged {case['age']}.
    Situation: {case['description']}

    Your symptoms: {case['symptoms']}
    What you do NOT have: {case.get('negative_features', '')}
    Your past medical history: {case.get('past_medical_history', '')}
    Your medications: {case.get('drug_history', '')}
    Your family history: {case.get('family_history', '')}
    Your social history: {case.get('social_history', '')}
    Your ideas about what is wrong: {case.get('ice', {}).get('ideas', '')}
    Your concerns: {case.get('ice', {}).get('concerns', '')}
    Your expectations: {case.get('ice', {}).get('expectations', '')}

    STRICT rules you must follow:
    - ONLY answer the specific question asked — nothing more
    - Do NOT volunteer extra information unprompted
    - Do NOT mention radiation unless asked where the pain spreads
    - Do NOT mention severity unless asked how bad it is
    - Do NOT mention associated symptoms unless directly asked
    - Respond in 1 to 2 sentences maximum
    - Speak naturally like a real patient
    - Never reveal the diagnosis
    - If asked something not in your case say you are not sure
    - If the student shows empathy or says something reassuring like I am sorry to hear that or don't worry, respond naturally and emotionally like a real patient would
    - If the student introduces themselves respond politely and naturally"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )

    patient_response = response.choices[0].message.content
    image = get_symptom_image(patient_response)

    return {
        "response": patient_response,
        "image": image
    }

def evaluate_checklist(conversation_history, checklist):
    results = {}
    total_possible = 0
    total_achieved = 0

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

def generate_overall_feedback(checklist_results, viva_scores, viva_questions, case_id):
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
            if not item["achieved"]:
                missed_items.append(item["item"])

    missed_str = ", ".join(missed_items[:5]) if missed_items else "None"

    prompt = f"""You are an experienced OSCE examiner giving feedback to a medical student.

Case: {case['description']}
Correct diagnosis: {case['correct_diagnosis']}

Student performance:
- Checklist score: {checklist_total} out of {checklist_possible}
- Viva score: {viva_total} out of {viva_possible}
- Overall score: {overall_total} out of {overall_possible}

Key checklist items the student missed: {missed_str}

Please provide:
1. Two sentences of positive feedback on what they did well
2. Two sentences on the main areas they need to improve
3. One sentence on the most important clinical point they should remember about this case

Keep the feedback encouraging, specific and clinically relevant. 
Total response should be 5-6 sentences maximum."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content