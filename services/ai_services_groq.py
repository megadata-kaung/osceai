from dotenv import load_dotenv
import os
import json
import requests

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


def clean_patient_response(text):
    """
    Clean and normalise AI response to ensure
    it sounds like a real patient consistently
    """
    if not text:
        return "I am not feeling well, doctor."

    # Remove common AI artifacts
    artifacts = [
        "As an AI", "As a language model", "I'm an AI",
        "I cannot roleplay", "I am unable",
        "As Sarah,", "As Margaret,", "As James,",
        "As John,", "As Michael,", "As Robert,",
        "As Emma,", "As George,", "As Thomas,",
        "Patient:", "Sarah:", "Margaret:", "James:",
        "John:", "Michael:", "Robert:", "Emma:",
        "George:", "Thomas:",
        "[", "]", "**",
        "Sure!", "Certainly!", "Of course!",
        "Great question!", "That's a good question",
        "I'd be happy to", "I'll play",
        "Here's my response:", "Response:",
    ]

    cleaned = text
    for artifact in artifacts:
        cleaned = cleaned.replace(artifact, "")

    # Remove extra whitespace
    cleaned = " ".join(cleaned.split())

    # Remove surrounding quotes
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]

    # Truncate to 2 sentences max
    sentences = cleaned.replace("!", ".").replace("?", ".").split(".")
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) > 2:
        cleaned = ". ".join(sentences[:2]) + "."

    # Final fallback if empty after cleaning
    if not cleaned.strip():
        return "I am sorry, could you repeat that please?"

    return cleaned.strip()


# ── Core AI call — Groq primary, Cohere fallback ──
def call_ai(messages, max_tokens=150, temperature=0.4):
    """
    Groq (primary) → Cohere (fallback)
    """

    # ── Attempt 1: Groq ──
    try:
        response = get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        print("[AI] Groq responded successfully")
        return response.choices[0].message.content
    except Exception as e:
        print(f"[AI] Groq failed: {e} — switching to Cohere")

    # ── Attempt 2: Cohere ──
    try:
        cohere_key = os.getenv("COHERE_API_KEY")
        if not cohere_key:
            raise Exception("COHERE_API_KEY not set")

        system_content = ""
        chat_history = []
        last_user_message = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                last_user_message = msg["content"]
                if chat_history:
                    chat_history.append({
                        "role": "USER",
                        "message": msg["content"]
                    })
            elif msg["role"] == "assistant":
                chat_history.append({
                    "role": "CHATBOT",
                    "message": msg["content"]
                })

        if chat_history and chat_history[-1]["role"] == "USER":
            last_user_message = chat_history[-1]["message"]
            chat_history = chat_history[:-1]

        if system_content:
            system_content += (
                "\n\nCRITICAL REMINDER: You are the patient. "
                "Reply ONLY as the patient. "
                "Maximum 2 sentences. "
                "No AI language. No preamble. "
                "Do not say 'As [name]' or 'As a patient'. "
                "Just speak directly as the patient would."
            )

        response = requests.post(
            "https://api.cohere.com/v1/chat",
            headers={
                "Authorization": "Bearer " + cohere_key,
                "Content-Type": "application/json"
            },
            json={
                "model": "command-r-plus-08-2024",
                "message": last_user_message,
                "preamble": system_content,
                "chat_history": chat_history,
                "max_tokens": max_tokens,
                "temperature": temperature
            },
            timeout=30
        )

        data = response.json()
        if "text" not in data:
            raise Exception(f"Unexpected response: {data}")
        print("[AI] Cohere responded successfully")
        return data["text"]

    except Exception as e:
        print(f"[AI] Cohere also failed: {e}")
        return (
            "I am sorry, I am having some difficulty. "
            "Please try again in a moment."
        )


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

Correct behaviour example:
Student: "What brings you in today?"
You: "I have been having really bad chest pain since this morning."

Wrong behaviour example:
Student: "What brings you in today?"
You: "I have chest pain that started this morning, it radiates to my left arm, I feel nauseous, I have hypertension and I take amlodipine."

Remember: answer one question at a time. Be natural. Be human."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    patient_response = call_ai(
        messages, max_tokens=80, temperature=0.3
    )

    # Clean response for consistency
    patient_response = clean_patient_response(patient_response)

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

    missed_str = (
        ", ".join(missed_items[:5]) if missed_items else "None"
    )

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

    messages = [{"role": "user", "content": prompt}]

    return call_ai(messages, max_tokens=300, temperature=0.4)