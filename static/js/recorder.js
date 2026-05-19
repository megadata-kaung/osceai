let selectedCaseId = null;
let isRecording = false;
let recognition = null;
let conversationHistory = [];
let patientAge = 30;
let patientGender = "female";
let currentTab = "chat";
let avatarRecognition = null;
let avatarRecording = false;
let practiceTimerInterval = null;
let practiceTimerSeconds = 0;
let practiceTimerRunning = false;
let voiceSpeedMultiplier = 1.0;

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

async function loadPatientInfo() {
    if (!selectedCaseId) return;
    try {
        const res = await fetch(
            `/get_full_case_info?case_id=${selectedCaseId}`
        );
        const data = await res.json();
        const name = document.getElementById("infoName");
        const age = document.getElementById("infoAge");
        const gender = document.getElementById("infoGender");
        const location = document.getElementById("infoLocation");
        const complaint = document.getElementById("infoComplaint");
        if (name) name.textContent = data.patient_name || "—";
        if (age) age.textContent = data.age || "—";
        if (gender) gender.textContent =
            data.gender === "female" ? "Female" : "Male";
        if (location) location.textContent = data.location || "—";
        if (complaint) complaint.textContent = data.complaint || "—";
    } catch (err) {
        console.error("Could not load patient info:", err);
    }
}

function selectCase(caseId, caseLabel) {
    const encodedLabel = encodeURIComponent(caseLabel);
    window.location.href =
        `/candidate_instructions?case_id=${caseId}&case_label=${encodedLabel}`;
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
    conversationHistory.push({ role: "user", content: message });

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
        if (sendBtn) {
            sendBtn.textContent = "Send";
            sendBtn.disabled = false;
        }
    })
    .catch(error => {
        addMessage(
            "Sorry, something went wrong. Please try again.",
            "patient"
        );
        console.error("Error:", error);
        if (sendBtn) {
            sendBtn.textContent = "Send";
            sendBtn.disabled = false;
        }
    });
}

function addMessage(text, sender) {
    const chatBox = document.getElementById("chatBox");
    if (!chatBox) return;
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ── Updated voice settings with speed multiplier ──
function getVoiceSettings() {
    let rate, pitch;

    if (patientGender === "female") {
        if (patientAge < 30) { rate = 1.1; pitch = 1.2; }
        else if (patientAge <= 50) { rate = 1.0; pitch = 1.05; }
        else { rate = 0.9; pitch = 0.95; }
    } else {
        if (patientAge < 30) { rate = 1.05; pitch = 1.0; }
        else if (patientAge <= 50) { rate = 0.95; pitch = 0.9; }
        else { rate = 0.88; pitch = 0.82; }
    }

    // Apply speed multiplier — clamp between 0.5 and 1.8
    rate = Math.max(0.5, Math.min(1.8, rate * voiceSpeedMultiplier));

    return { rate, pitch };
}

// ── Voice always respects patient gender ──
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
        "alex", "fred", "thomas", "google uk english male"
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

// ── Voice speed control ──
function setVoiceSpeed(speed, btn) {
    if (speed === "slow") voiceSpeedMultiplier = 0.82;
    else if (speed === "normal") voiceSpeedMultiplier = 1.0;
    else if (speed === "fast") voiceSpeedMultiplier = 1.2;

    // Update active button
    document.querySelectorAll(".voice-speed-btn").forEach(b =>
        b.classList.remove("active"));
    btn.classList.add("active");

    // Save preference
    sessionStorage.setItem("voiceSpeed", speed);
}

function loadVoicePreferences() {
    const savedSpeed = sessionStorage.getItem("voiceSpeed") || "normal";

    if (savedSpeed === "slow") voiceSpeedMultiplier = 0.82;
    else if (savedSpeed === "normal") voiceSpeedMultiplier = 1.0;
    else if (savedSpeed === "fast") voiceSpeedMultiplier = 1.2;

    // Highlight correct button
    document.querySelectorAll(".voice-speed-btn").forEach(btn => {
        btn.classList.remove("active");
        const btnText = btn.textContent.toLowerCase();
        if (btnText.includes(savedSpeed)) {
            btn.classList.add("active");
        }
    });
}

function toggleMic() {
    if (!('webkitSpeechRecognition' in window ||
          'SpeechRecognition' in window)) {
        alert("Voice input not supported. Please use Chrome.");
        return;
    }
    if (isRecording) {
        recognition.stop();
        isRecording = false;
        document.getElementById("micBtn").classList.remove("recording");
    } else {
        recognition = new (window.SpeechRecognition ||
                           window.webkitSpeechRecognition)();
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
    if (event.key === "Enter") sendMessage();
}

function endSession() {
    if (!selectedCaseId) {
        alert("Please select a case first!");
        return;
    }
    sessionStorage.setItem("conversation",
        JSON.stringify(conversationHistory));
    sessionStorage.setItem("caseId", selectedCaseId);
    const caseLabel = document.getElementById("caseLabel");
    if (caseLabel) {
        sessionStorage.setItem("caseLabel", caseLabel.textContent);
    }
    window.location.href = `/post_check?case_id=${selectedCaseId}`;
}

function switchTab(tab) {
    currentTab = tab;
    const chatPanel = document.getElementById("chatPanel");
    const avatarPanel = document.getElementById("avatarPanel");
    const tabChat = document.getElementById("tabChat");
    const tabAvatar = document.getElementById("tabAvatar");

    if (tab === "chat") {
        if (chatPanel) chatPanel.style.display = "block";
        if (avatarPanel) avatarPanel.style.display = "none";
        if (tabChat) tabChat.classList.add("active");
        if (tabAvatar) tabAvatar.classList.remove("active");
    } else {
        if (chatPanel) chatPanel.style.display = "none";
        if (avatarPanel) avatarPanel.style.display = "flex";
        if (tabChat) tabChat.classList.remove("active");
        if (tabAvatar) tabAvatar.classList.add("active");
        loadAvatar();
    }
}

async function loadAvatar() {
    if (!selectedCaseId) return;
    try {
        const res = await fetch(
            `/get_case_info?case_id=${selectedCaseId}`
        );
        const data = await res.json();
        const img = document.getElementById("avatarImg");
        const nameTag = document.getElementById("avatarNameTag");
        if (img) {
            img.src = `/static/images/avatars/${selectedCaseId}.svg`;
        }
        if (nameTag) {
            nameTag.textContent = `${data.patient_name}, ${data.age}`;
        }
    } catch (err) {
        console.error("Could not load avatar:", err);
    }
}

function sendAvatarMessage() {
    const input = document.getElementById("avatarInput");
    const message = input.value.trim();
    if (!message) return;
    if (!selectedCaseId) return;

    input.value = "";
    const speechBubble = document.getElementById("avatarSpeech");
    const statusEl = document.getElementById("avatarStatus");
    const wrapper = document.getElementById("avatarWrapper");

    if (speechBubble) speechBubble.textContent = "...";
    if (statusEl) {
        statusEl.textContent = "Thinking...";
        statusEl.className = "avatar-status";
    }

    conversationHistory.push({ role: "user", content: message });

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
        addMessage(message, "student");
        addMessage(data.response, "patient");

        if (speechBubble) speechBubble.textContent = data.response;
        if (statusEl) {
            statusEl.textContent = "Speaking...";
            statusEl.className = "avatar-status talking";
        }
        if (wrapper) wrapper.classList.add("avatar-talking");

        conversationHistory.push({
            role: "assistant",
            content: data.response
        });

        speakResponse(data.response);

        setTimeout(() => {
            if (wrapper) wrapper.classList.remove("avatar-talking");
            if (statusEl) {
                statusEl.textContent = "Waiting for your question...";
                statusEl.className = "avatar-status";
            }
        }, data.response.length * 60);
    })
    .catch(err => {
        console.error(err);
        if (statusEl) statusEl.textContent = "Error — please try again";
        if (speechBubble) {
            speechBubble.textContent =
                "Something went wrong. Please try again.";
        }
    });
}

function handleAvatarEnter(event) {
    if (event.key === "Enter") sendAvatarMessage();
}

function toggleAvatarMic() {
    if (!('webkitSpeechRecognition' in window ||
          'SpeechRecognition' in window)) {
        alert("Please use Chrome for voice input.");
        return;
    }
    if (avatarRecording) {
        avatarRecognition.stop();
        avatarRecording = false;
        document.getElementById("avatarMicBtn")
            .classList.remove("recording");
    } else {
        avatarRecognition = new (window.SpeechRecognition ||
                                  window.webkitSpeechRecognition)();
        avatarRecognition.lang = "en-US";
        avatarRecognition.continuous = false;
        avatarRecognition.interimResults = false;
        avatarRecognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            document.getElementById("avatarInput").value = transcript;
        };
        avatarRecognition.onend = function() {
            avatarRecording = false;
            document.getElementById("avatarMicBtn")
                .classList.remove("recording");
        };
        avatarRecognition.start();
        avatarRecording = true;
        document.getElementById("avatarMicBtn").classList.add("recording");
    }
}

function togglePracticeTimer() {
    if (practiceTimerRunning) {
        clearInterval(practiceTimerInterval);
        practiceTimerRunning = false;
        const btn = document.getElementById("timerToggleBtn");
        if (btn) btn.textContent = "▶ Start Timer";
    } else {
        practiceTimerRunning = true;
        const btn = document.getElementById("timerToggleBtn");
        if (btn) btn.textContent = "⏸ Pause Timer";
        practiceTimerInterval = setInterval(() => {
            practiceTimerSeconds++;
            updatePracticeTimerDisplay();
        }, 1000);
    }
}

function updatePracticeTimerDisplay() {
    const mins = Math.floor(practiceTimerSeconds / 60);
    const secs = practiceTimerSeconds % 60;
    const display =
        `${String(mins).padStart(2,"0")}:${String(secs).padStart(2,"0")}`;
    const timerEl = document.getElementById("timerDisplay");
    if (timerEl) timerEl.textContent = display;

    const maxSeconds = 480;
    const pct = Math.min(
        (practiceTimerSeconds / maxSeconds) * 100, 100
    );
    const fill = document.getElementById("timerBarFill");
    if (!fill) return;
    fill.style.width = pct + "%";

    if (practiceTimerSeconds < 300) {
        fill.style.background = "#2c7be5";
        if (timerEl) timerEl.style.color = "#2c7be5";
    } else if (practiceTimerSeconds < 420) {
        fill.style.background = "#f6a623";
        if (timerEl) timerEl.style.color = "#f6a623";
    } else {
        fill.style.background = "#e74c3c";
        if (timerEl) timerEl.style.color = "#e74c3c";
    }

    const labelEl = document.getElementById("timerLabel");
    if (practiceTimerSeconds === 480 && labelEl) {
        labelEl.textContent = "⚠️ 8 minutes — wrap up!";
    }
}

function clearNotes() {
    const notes = document.getElementById("studentNotes");
    if (notes) notes.value = "";
}

window.onload = async function() {
    const params = new URLSearchParams(window.location.search);
    const caseId = params.get("case_id");
    const caseLabel = params.get("case_label");

    if (caseId) {
        selectedCaseId = caseId;

        await loadPatientVoiceProfile();
        await loadPatientInfo();

        const labelEl = document.getElementById("caseLabel");
        if (labelEl && caseLabel) {
            labelEl.textContent = decodeURIComponent(caseLabel);
        }

        const caseSelection = document.getElementById("caseSelection");
        const simulationPanel = document.getElementById("simulationPanel");
        const simFooter = document.getElementById("simFooter");
        const simTabs = document.getElementById("simTabs");
        const voiceControls = document.getElementById("voiceControls");

        if (caseSelection) caseSelection.style.display = "none";
        if (simulationPanel) simulationPanel.style.display = "flex";
        if (simFooter) simFooter.style.display = "flex";
        if (simTabs) simTabs.style.display = "flex";
        if (voiceControls) voiceControls.style.display = "flex";

        switchTab("chat");
        loadVoicePreferences();

        const savedNotes = sessionStorage.getItem("candidateNotes");
        const notesEl = document.getElementById("studentNotes");
        if (savedNotes && notesEl) {
            notesEl.value = savedNotes;
        }
    }
};
function setVoiceSpeed(speed, btn) {
    if (speed === "slow") voiceSpeedMultiplier = 0.82;
    else if (speed === "normal") voiceSpeedMultiplier = 1.0;
    else if (speed === "fast") voiceSpeedMultiplier = 1.2;

    document.querySelectorAll(".voice-speed-pill").forEach(b =>
        b.classList.remove("active"));
    btn.classList.add("active");

    const hint = document.getElementById("voiceSpeedHint");
    if (hint) {
        if (speed === "slow") hint.textContent = "🐢 Slower speech";
        else if (speed === "normal") hint.textContent = "✓ Normal speed";
        else if (speed === "fast") hint.textContent = "⚡ Faster speech";
    }

    sessionStorage.setItem("voiceSpeed", speed);
}

function loadVoicePreferences() {
    const savedSpeed = sessionStorage.getItem("voiceSpeed") || "normal";

    if (savedSpeed === "slow") voiceSpeedMultiplier = 0.82;
    else if (savedSpeed === "normal") voiceSpeedMultiplier = 1.0;
    else if (savedSpeed === "fast") voiceSpeedMultiplier = 1.2;

    document.querySelectorAll(".voice-speed-pill").forEach(btn => {
        btn.classList.remove("active");
        const btnText = btn.textContent.toLowerCase().trim();
        if (btnText === savedSpeed) {
            btn.classList.add("active");
        }
    });

    const hint = document.getElementById("voiceSpeedHint");
    if (hint) {
        if (savedSpeed === "slow") hint.textContent = "🐢 Slower speech";
        else if (savedSpeed === "normal") hint.textContent = "✓ Normal speed";
        else if (savedSpeed === "fast") hint.textContent = "⚡ Faster speech";
    }
}