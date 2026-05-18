let selectedCaseId = null;
let isRecording = false;
let recognition = null;
let conversationHistory = [];
let patientAge = 30;
let patientGender = "female";

async function loadPatientVoiceProfile() {
    if (!selectedCaseId) return;
    try {
        const res = await fetch(`/get_case_info?case_id=${selectedCaseId}`);
        const data = await res.json();
        patientAge = data.age || 30;
        patientGender = data.gender || "female";
    } catch (err) {
        console.error("Could not load patient profile:", err);
    }
}

function selectCase(caseId, caseLabel) {
    const encodedLabel = encodeURIComponent(caseLabel);
    window.location.href = `/pre_check?case_id=${caseId}&case_label=${encodedLabel}`;
}

function sendMessage() {
    const input = document.getElementById("userInput");
    const message = input.value.trim();
    if (!message) return;
    if (!selectedCaseId) {
        alert("Please select a case first!");
        return;
    }

    addMessage(message, "student");
    input.value = "";

    conversationHistory.push({
        role: "user",
        content: message
    });

    const sendBtn = document.querySelector(".btn-send");
    if (sendBtn) {
        sendBtn.textContent = "...";
        sendBtn.disabled = true;
    }

    fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            message: message,
            case_id: selectedCaseId
        })
    })
    .then(res => res.json())
    .then(data => {
        addMessage(data.response, "patient");
        speakResponse(data.response);

        conversationHistory.push({
            role: "assistant",
            content: data.response
        });

        if (data.image) {
            showAnatomyImage(data.image);
        }

        if (sendBtn) {
            sendBtn.textContent = "Send";
            sendBtn.disabled = false;
        }
    })
    .catch(error => {
        addMessage("Sorry, something went wrong. Please try again.", "patient");
        console.error("Error:", error);
        if (sendBtn) {
            sendBtn.textContent = "Send";
            sendBtn.disabled = false;
        }
    });
}

function addMessage(text, sender) {
    const chatBox = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function getVoiceSettings() {
    let rate, pitch;

    if (patientGender === "female") {
        if (patientAge < 30) {
            rate = 1.05; pitch = 1.3;
        } else if (patientAge <= 50) {
            rate = 0.92; pitch = 1.1;
        } else {
            rate = 0.78; pitch = 0.95;
        }
    } else {
        if (patientAge < 30) {
            rate = 1.0;  pitch = 1.0;
        } else if (patientAge <= 50) {
            rate = 0.88; pitch = 0.85;
        } else {
            rate = 0.75; pitch = 0.75;
        }
    }

    return { rate, pitch };
}

function getBestVoice(gender) {
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;

    const femaleKeywords = [
        "female", "woman", "zira", "samantha", "karen",
        "victoria", "moira", "fiona", "kate", "susan",
        "google uk english female", "google us english"
    ];

    const maleKeywords = [
        "male", "man", "david", "daniel", "mark",
        "alex", "fred", "thomas",
        "google uk english male"
    ];

    const keywords = gender === "female" ? femaleKeywords : maleKeywords;
    let bestVoice = null;

    for (const keyword of keywords) {
        bestVoice = voices.find(v =>
            v.name.toLowerCase().includes(keyword) &&
            v.lang.startsWith("en")
        );
        if (bestVoice) break;
    }

    if (!bestVoice) {
        bestVoice = voices.find(v => v.lang.startsWith("en")) || voices[0];
    }

    return bestVoice;
}

function speakResponse(text) {
    window.speechSynthesis.cancel();

    const settings = getVoiceSettings();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = settings.rate;
    utterance.pitch = settings.pitch;
    utterance.lang = "en-GB";

    const voices = window.speechSynthesis.getVoices();

    if (voices.length === 0) {
        window.speechSynthesis.onvoiceschanged = function() {
            const voice = getBestVoice(patientGender);
            if (voice) utterance.voice = voice;
            window.speechSynthesis.speak(utterance);
        };
    } else {
        const voice = getBestVoice(patientGender);
        if (voice) utterance.voice = voice;
        window.speechSynthesis.speak(utterance);
    }
}

function showAnatomyImage(imageName) {
    const display = document.getElementById("anatomyDisplay");
    display.innerHTML = `<img src="/static/images/${imageName}"
                         alt="Anatomy reference"
                         style="max-width:100%; border-radius:8px;"/>`;
}

function toggleMic() {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        alert("Your browser does not support voice input. Please use Chrome.");
        return;
    }

    if (isRecording) {
        recognition.stop();
        isRecording = false;
        document.getElementById("micBtn").classList.remove("recording");
    } else {
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = "en-US";
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            document.getElementById("userInput").value = transcript;
        };

        recognition.onend = function() {
            isRecording = false;
            document.getElementById("micBtn").classList.remove("recording");
        };

        recognition.onerror = function(event) {
            console.error("Mic error:", event.error);
            isRecording = false;
            document.getElementById("micBtn").classList.remove("recording");
        };

        recognition.start();
        isRecording = true;
        document.getElementById("micBtn").classList.add("recording");
    }
}

function handleEnter(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

function endSession() {
    if (!selectedCaseId) {
        alert("Please select a case first!");
        return;
    }

    sessionStorage.setItem("conversation", JSON.stringify(conversationHistory));
    sessionStorage.setItem("caseId", selectedCaseId);

    const caseLabel = document.getElementById("caseLabel").textContent;
    sessionStorage.setItem("caseLabel", caseLabel);

    window.location.href = `/post_check?case_id=${selectedCaseId}`;
}

window.onload = async function() {
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case_id");
    const caseLabel = params.get("case_label");

    if (caseId) {
        selectedCaseId = caseId;
        await loadPatientVoiceProfile();

        const labelEl = document.getElementById("caseLabel");
        if (labelEl && caseLabel) {
            labelEl.textContent = decodeURIComponent(caseLabel);
        }

        const caseSelection = document.getElementById("caseSelection");
        const simulationPanel = document.getElementById("simulationPanel");
        const simFooter = document.getElementById("simFooter");

        if (caseSelection) caseSelection.style.display = "none";
        if (simulationPanel) simulationPanel.style.display = "flex";
        if (simFooter) simFooter.style.display = "flex";
    }
};