const form = document.querySelector("#question-form");
const input = document.querySelector("#question-input");
const messages = document.querySelector("#messages");
const statusLabel = document.querySelector("#form-status");
const sendButton = document.querySelector("#send-button");
const voiceButton = document.querySelector("#voice-button");
const voiceConversationButton = document.querySelector("#voice-conversation-button");
const loboAvatar = document.querySelector(".lobo-avatar");
const avatarError = document.querySelector("#avatar-error");
const avatarSpeaking = document.querySelector("#avatar-speaking");
const voiceCaption = document.querySelector("#voice-caption");
const voiceCaptionText = document.querySelector("#voice-caption-text");
const captionToggle = document.querySelector("#caption-toggle");
const repeatResponseButton = document.querySelector("#repeat-response");
const contactDialog = document.querySelector("#contact-dialog");
const contactForm = document.querySelector("#contact-form");
const contactStatus = document.querySelector("#contact-status");
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;
let recognitionMode = "dictation";
let voiceConversationActive = false;
let voiceTurnPending = false;
let voiceTranscriptTimer = null;
let voiceRestartTimer = null;
let dictationActive = false;
let dictationSubmitRequested = false;
let dictationBaseText = "";
let dictationFinalText = "";
let dictationRestartTimer = null;
let dictationSilenceTimer = null;
let dictationStartedAt = 0;
let kioskSpeechVoice = null;
let subtitlesEnabled = true;
try { subtitlesEnabled = localStorage.getItem("lobo_kiosk_subtitles") !== "false"; } catch { /* Usa subtítulos si el navegador bloquea el almacenamiento. */ }
let lastAssistantResponse = messages.querySelector(".assistant-message p")?.textContent?.trim() || "";
let announcements = [];
let announcementIndex = 0;
let announcementTimer = null;
let announcementPaused = false;
let announcementUserPaused = false;
let speechAudioContext = null;
let speechAudioSources = [];
let speechScheduleEnd = 0;
let speechStreamStarted = false;
let speechFileAudio = null;
let speechStreamReader = null;
let speechRequestController = null;
let speechGeneration = 0;
let avatarMotionTimer = null;
let greetingGestureTimer = null;

// Duraciones de los clips incluidos en buggy-upvt-animated.glb. El saludo debe
// poder terminar aunque la voz de respuesta sea más corta.
const avatarClipDurations = {
    Idle: 3,
    Hablar: 1.3,
    Explicar: 1.8,
    Pensar: 1.3,
    Saludo: 2.834,
    Celebrar: 1.292,
    Presentar: 1.9,
    Senalar: 1.4,
    Asentir: 1.17,
    Escuchar: 1.3,
};

function prepareSpeechAudio() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    try {
        speechAudioContext ||= new AudioContextClass();
        if (speechAudioContext.state === "suspended") void speechAudioContext.resume().catch(() => {});
    } catch {
        speechAudioContext = null;
    }
}

function stopAvatarMotion() {
    window.clearTimeout(avatarMotionTimer);
    avatarMotionTimer = null;
    window.clearTimeout(greetingGestureTimer);
    greetingGestureTimer = null;
    if (!loboAvatar?.loaded) return;
    // No pausarlo en el bind pose: el GLB de origen está en T. Idle fija una
    // postura relajada y estática, con los brazos abajo, hasta la interacción.
    if (!playAvatarAnimation("Idle", { loop: true })) {
        loboAvatar.removeAttribute("loop");
        loboAvatar.pause();
        loboAvatar.currentTime = 0;
    }
}

function cancelSpeechAudio() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    speechRequestController?.abort();
    speechRequestController = null;
    if (speechStreamReader) void speechStreamReader.cancel().catch(() => {});
    speechStreamReader = null;
    if (speechFileAudio) {
        speechFileAudio.pause();
        speechFileAudio.currentTime = 0;
        speechFileAudio = null;
    }
    for (const source of speechAudioSources) {
        try { source.stop(); } catch { /* La fuente ya terminó. */ }
    }
    speechAudioSources = [];
    speechScheduleEnd = 0;
    speechStreamStarted = false;
    setAvatarSpeaking(false);
}

function stopSpeech() {
    speechGeneration++;
    cancelSpeechAudio();
    stopAvatarMotion();
}

function setAvatarSpeaking(speaking) {
    if (avatarSpeaking) avatarSpeaking.hidden = !speaking;
    document.querySelector(".avatar-stage")?.classList.toggle("is-speaking", speaking);
}

function setSubtitlesEnabled(enabled) {
    subtitlesEnabled = enabled;
    captionToggle?.setAttribute("aria-pressed", String(enabled));
    if (captionToggle) captionToggle.textContent = `Subtítulos: ${enabled ? "activados" : "desactivados"}`;
    if (voiceCaptionText) voiceCaptionText.hidden = !enabled;
    voiceCaption?.classList.toggle("subtitles-off", !enabled);
    try { localStorage.setItem("lobo_kiosk_subtitles", String(enabled)); } catch { /* La preferencia es opcional. */ }
}

setSubtitlesEnabled(subtitlesEnabled);
captionToggle?.addEventListener("click", () => setSubtitlesEnabled(!subtitlesEnabled));
document.querySelector("#text-smaller")?.addEventListener("click", () => {
    document.querySelector('[data-a11y-action="smaller"]')?.click();
});
document.querySelector("#text-larger")?.addEventListener("click", () => {
    document.querySelector('[data-a11y-action="larger"]')?.click();
});
repeatResponseButton?.addEventListener("click", () => {
    if (lastAssistantResponse) {
        prepareSpeechAudio();
        void speakResponse(lastAssistantResponse, "Hablar");
    }
});

function normalizeAvatarText(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

function casualKioskResponse(message) {
    const normalized = normalizeAvatarText(message)
        .replace(/\bhona\b/g, "hola")
        .replace(/\bq\b/g, "que")
        .replace(/[^a-z0-9 ]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    const greeting = "(?:hola|ola|holi|oli|hey|ey|saludos|buenas tardes|buenas noches|buenos dias|buen dia|buenas)";
    const greetingWithName = new RegExp(`^${greeting}(?: lobo)?$`);
    const greetingAndSmallTalk = new RegExp(
        `^${greeting}(?: lobo)? (?:como estas|como esta|como te encuentras|como te va|como andas|que tal(?: estas)?|que onda(?: lobo)?|todo bien)$`,
    );
    const greetingPrefix = /^(?:(?:hola|ola|holi|oli|hey|ey|saludos|buenas tardes|buenas noches|buenos dias|buen dia|buenas)(?: lobo)?\s*)+/;
    const socialText = normalized.replace(greetingPrefix, "").trim() || normalized;

    if (greetingAndSmallTalk.test(normalized)
        || /^(?:como estas|como esta|como te encuentras|como te va|como andas|todo bien|bien y tu|bien y tu lobo)$/.test(socialText)) {
        return "¡Muy bien, gracias por preguntar! Aquí estoy para ayudarte con la UPVT. ¿Qué te gustaría saber?";
    }
    if (/^(?:que tal|que tal lobo|que onda|que onda lobo)$/.test(socialText)) {
        return "¡Todo bien por aquí! Qué gusto saludarte. ¿Qué te gustaría consultar de la UPVT?";
    }
    if (greetingWithName.test(normalized)) {
        return "¡Hola! Qué gusto saludarte. Soy Lobo, el asistente de la UPVT. ¿En qué te puedo ayudar?";
    }
    if (/^(?:que haces|que cuentas|como va todo|todo tranquilo)$/.test(socialText)) {
        return "Aquí ando, listo para ayudarte con lo que necesites de la UPVT. ¿Qué te gustaría consultar?";
    }
    if (/^(?:quien eres|como te llamas)$/.test(socialText)) {
        return "Soy Lobo, el asistente virtual de la UPVT. Puedo ayudarte con información de la universidad.";
    }
    if (/^(?:gracias|muchas gracias|te lo agradezco|gracias lobo)$/.test(socialText)) {
        return "¡Con gusto! Aquí estoy por si necesitas algo más.";
    }
    if (/^(?:adios|hasta luego|nos vemos|bye|adios lobo)$/.test(socialText)) {
        return "¡Hasta luego! Que tengas un excelente día. Aquí estaré si necesitas información de la UPVT.";
    }
    return null;
}

function selectKioskSpeechVoice() {
    if (!window.speechSynthesis) return null;
    const voices = window.speechSynthesis.getVoices();
    const spanishVoices = voices.filter((voice) => /^es(?:-|_)/i.test(voice.lang));
    const masculineSpanishVoices = spanishVoices.filter((voice) => /jorge|raul|raúl|pablo|miguel|male|mascul/i.test(voice.name));
    kioskSpeechVoice = masculineSpanishVoices.find((voice) => /natural|online|neural/i.test(voice.name))
        || masculineSpanishVoices.find((voice) => /^es-MX/i.test(voice.lang))
        || spanishVoices.find((voice) => /natural|online|neural/i.test(voice.name) && /mascul|male/i.test(voice.name))
        || spanishVoices.find((voice) => /^es-MX/i.test(voice.lang))
        || voices.find((voice) => /^es-MX/i.test(voice.lang))
        || spanishVoices[0]
        || null;
    return kioskSpeechVoice;
}

window.speechSynthesis?.addEventListener("voiceschanged", selectKioskSpeechVoice);
selectKioskSpeechVoice();

function playAvatarAnimation(requestedName, { loop = false } = {}) {
    if (!loboAvatar) return false;
    const available = Array.isArray(loboAvatar.availableAnimations)
        ? loboAvatar.availableAnimations
        : [];
    const requested = normalizeAvatarText(requestedName);
    const selectedClip = available.find((name) => normalizeAvatarText(name) === requested)
        || available.find((name) => normalizeAvatarText(name).includes(requested))
        || null;
    const fallbackClip = available.length
        ? available.find((name) => normalizeAvatarText(name) === "hablar")
            || available.find((name) => normalizeAvatarText(name) === "explicar")
            || available.find((name) => normalizeAvatarText(name) !== "idle")
            || available[0]
        : null;
    const clip = selectedClip || fallbackClip || ["Idle", "Hablar", "Explicar", "Pensar", "Saludo", "Celebrar", "Presentar", "Senalar", "Asentir", "Escuchar"]
        .find((name) => normalizeAvatarText(name) === requested);
    if (!clip) return false;

    loboAvatar.removeAttribute("loop");
    if (loop) loboAvatar.setAttribute("loop", "");
    // El atributo es la interfaz que model-viewer documenta para elegir clip;
    // se asigna explícitamente además de la propiedad para que ambos queden sincronizados.
    loboAvatar.setAttribute("animation-name", clip);
    loboAvatar.animationName = clip;
    loboAvatar.currentTime = 0;
    loboAvatar.play();
    window.clearTimeout(avatarMotionTimer);
    avatarMotionTimer = null;
    if (!loop && clip !== "Idle") {
        avatarMotionTimer = window.setTimeout(() => {
            avatarMotionTimer = null;
            if (loboAvatar?.loaded) playAvatarAnimation("Idle", { loop: true });
        }, Math.ceil((avatarClipDurations[clip] || 2.9) * 1000) + 100);
    }
    return true;
}

function shouldLoopAvatarAnimation(name) {
    // Hablar es un gesto continuo; saludos y gestos con principio/fin se
    // ejecutan una sola vez para no reiniciar el brazo desde el reposo.
    return name === "Hablar" || name === "Explicar";
}

function animationForReply(payload, question) {
    const action = normalizeAvatarText(payload?.accion_avatar || "");
    if (/salud|desped|wave|bienven/.test(action)) return "Saludo";
    if (/senal|indica|apunta|apuntar/.test(action)) return "Senalar";
    if (/escuch|oreja/.test(action)) return "Escuchar";
    if (/asient|afirma|inclina la cabeza|mueve la cabeza afirm/.test(action)) return "Asentir";
    if (/presenta|abre ambas manos|abre los brazos|palmas abiertas/.test(action)) return "Presentar";
    if (/celebr|festej|aplaud/.test(action)) return "Celebrar";
    if (/piensa|reflexiona|duda/.test(action)) return "Pensar";
    if (/explica|expone|gestos suaves de ambas manos/.test(action)) return "Explicar";

    const selectedAnimation = normalizeAvatarText(payload?.animacion || "");
    const selectedClips = {
        hablar: "Hablar",
        explicar: "Explicar",
        saludo: "Saludo",
        pensar: "Pensar",
        celebrar: "Celebrar",
        // Reposo es solo para cuando no hay interacción; al contestar se usa
        // un gesto de habla para que el avatar no parezca congelado.
        idle: "Hablar",
        reposo: "Hablar",
        greeting: "Saludo",
        thinking: "Pensar",
        celebrate: "Celebrar",
        presentar: "Presentar",
        mostrar: "Presentar",
        senalar: "Senalar",
        indicar: "Senalar",
        asentir: "Asentir",
        escuchar: "Escuchar",
    };
    if (selectedClips[selectedAnimation]) return selectedClips[selectedAnimation];
    const metadata = normalizeAvatarText(`${payload?.animacion || ""} ${payload?.emocion || ""} ${payload?.accion_avatar || ""}`);
    if (/salud|greet|bienvenid|hola/.test(metadata)) return "Saludo";
    if (/pens|think|duda|reflex/.test(metadata)) return "Pensar";
    if (/celebr|festej|aplaud|bail/.test(metadata)) return "Celebrar";
    if (/explic|orient|presenta|curricular|materia|cuatrimestre/.test(`${metadata} ${normalizeAvatarText(question)}`)) return "Explicar";
    return "Explicar";
}

function newRequestId() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `kiosk-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function requestChat(message, context = [], requestId = newRequestId()) {
    let lastError;
    for (let attempt = 0; attempt < 2; attempt++) {
        try {
            const response = await fetch("/api/v1/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mensaje: message, contexto: context, request_id: requestId }),
                signal: AbortSignal.timeout(6500),
            });
            const payload = await response.json().catch(() => ({}));
            if (response.ok) return payload;
            const error = new Error(payload.detail || "No se pudo consultar la información.");
            error.retryable = response.status >= 500;
            throw error;
        } catch (error) {
            lastError = error;
            if (error.name === "AbortError" || error.name === "TimeoutError") throw error;
            const retryable = error.retryable === true || error instanceof TypeError;
            if (attempt >= 1 || !retryable) throw error;
            statusLabel.textContent = "Conexión interrumpida. Reintentando…";
            const label = document.querySelector("#connection-label");
            if (label) label.textContent = "Reconectando…";
            await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
    }
    throw lastError || new Error("No se pudo consultar la información.");
}

if (loboAvatar) {
    loboAvatar.addEventListener("load", () => {
        avatarError.hidden = true;
        stopAvatarMotion();
    });
    loboAvatar.addEventListener("error", () => { avatarError.hidden = false; });
    window.customElements?.whenDefined("model-viewer").then(() => {
        if (loboAvatar.loaded) avatarError.hidden = true;
    });
}

document.querySelector("#contact-open")?.addEventListener("click", () => {
    contactStatus.textContent = "";
    contactDialog.showModal();
    contactForm.elements.nombre.focus();
});
document.querySelector("#contact-close")?.addEventListener("click", () => contactDialog.close());
contactForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = contactForm.querySelector('[type="submit"]');
    submit.disabled = true;
    contactStatus.textContent = "Enviando mensaje…";
    contactStatus.className = "contact-status";
    const values = Object.fromEntries(new FormData(contactForm));
    try {
        const response = await fetch("/api/v1/contacto", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(values),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || "No se pudo enviar el mensaje. Intenta de nuevo.");
        contactForm.reset();
        contactStatus.textContent = payload.mensaje || "Gracias por escribirnos. Recibimos tu mensaje.";
        contactStatus.classList.add("success");
    } catch (error) {
        contactStatus.textContent = error.message || "No se pudo enviar el mensaje. Revisa tu conexión.";
        contactStatus.classList.add("error");
    } finally {
        submit.disabled = false;
    }
});

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "es-MX";
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
        isListening = true;
        if (recognitionMode === "conversation") {
            voiceConversationButton.classList.add("recording");
            voiceConversationButton.querySelector("span").textContent = "Te escucho…";
            statusLabel.textContent = "Te escucho. Habla con Lobo cuando quieras.";
        } else {
            voiceButton.classList.add("recording");
            voiceButton.setAttribute("aria-label", "Terminar dictado y enviar pregunta");
            voiceButton.querySelector("span").textContent = "Terminar dictado";
            statusLabel.textContent = "Te escucho. Puedes hacer una pausa; pulsa Terminar dictado cuando acabes.";
        }
        statusLabel.className = "";
    };

    recognition.onresult = (event) => {
        if (recognitionMode === "conversation") {
            const finalized = [];
            for (let index = event.resultIndex; index < event.results.length; index++) {
                const result = event.results[index];
                if (result.isFinal && result[0]?.transcript) finalized.push(result[0].transcript.trim());
            }
            if (!finalized.length) return;
            input.value = [input.value.trim(), finalized.join(" ")].filter(Boolean).join(" ");
            statusLabel.textContent = "Procesando lo que dijiste…";
            statusLabel.className = "";
            window.clearTimeout(voiceTranscriptTimer);
            voiceTranscriptTimer = window.setTimeout(() => {
                if (!voiceConversationActive || sendButton.disabled || input.value.trim().length < 2) return;
                voiceTurnPending = true;
                if (isListening) recognition.stop();
                form.requestSubmit();
            }, 750);
            return;
        }

        const finalized = [];
        const interim = [];
        for (let index = event.resultIndex; index < event.results.length; index++) {
            const result = event.results[index];
            const phrase = result[0]?.transcript?.trim();
            if (!phrase) continue;
            (result.isFinal ? finalized : interim).push(phrase);
        }
        if (finalized.length) {
            dictationFinalText = [dictationFinalText, ...finalized].filter(Boolean).join(" ");
        }
        input.value = [dictationBaseText, dictationFinalText, interim.join(" ")].filter(Boolean).join(" ");
        if (input.value.trim()) {
            statusLabel.textContent = "Te escucho… Si necesitas más tiempo, sigue hablando; al terminar pulsa Terminar dictado.";
            statusLabel.className = "";
        }
        if (dictationFinalText && (finalized.length || interim.length)) {
            window.clearTimeout(dictationSilenceTimer);
            dictationSilenceTimer = window.setTimeout(() => {
                if (!dictationActive) return;
                dictationSubmitRequested = true;
                if (isListening) recognition.stop();
                else finishDictation(true);
            }, 3500);
        }
    };

    recognition.onerror = (event) => {
        if (recognitionMode === "conversation" && event.error === "no-speech") return;
        if (recognitionMode === "dictation" && dictationActive && event.error === "no-speech") {
            statusLabel.textContent = "Aún te escucho. Habla cuando quieras.";
            statusLabel.className = "";
            return;
        }
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
            statusLabel.textContent = "Permite el acceso al micrófono en Edge para usar la conversación por voz.";
            if (recognitionMode === "conversation") stopVoiceConversation();
            else if (dictationActive) finishDictation(false);
        } else if (event.error === "no-speech") {
            statusLabel.textContent = "No se detectó voz. Pulsa Dictar e intenta de nuevo.";
        } else if (event.error !== "aborted") {
            statusLabel.textContent = recognitionMode === "conversation"
                ? "No se pudo mantener el micrófono activo. Vuelve a iniciar la conversación por voz."
                : "No se pudo reconocer la voz. Puedes escribir tu pregunta.";
            if (recognitionMode === "conversation") stopVoiceConversation();
            else if (dictationActive) finishDictation(false);
        }
        statusLabel.className = "error";
    };

    recognition.onend = () => {
        isListening = false;
        if (recognitionMode === "dictation" && dictationActive) {
            if (dictationSubmitRequested) {
                finishDictation(true);
            } else if (performance.now() - dictationStartedAt < 60000) {
                window.clearTimeout(dictationRestartTimer);
                dictationRestartTimer = window.setTimeout(() => {
                    if (!dictationActive || isListening) return;
                    try { recognition.start(); }
                    catch { finishDictation(Boolean(dictationFinalText.trim())); }
                }, 350);
            } else {
                finishDictation(Boolean(dictationFinalText.trim()));
            }
            return;
        }
        voiceButton.classList.remove("recording");
        voiceButton.setAttribute("aria-label", "Dictar pregunta por voz");
        voiceButton.querySelector("span").textContent = "Dictar";
        if (recognitionMode === "conversation" && voiceConversationActive) {
            voiceConversationButton.classList.remove("recording");
            if (voiceTurnPending || sendButton.disabled) {
                voiceConversationButton.querySelector("span").textContent = "Lobo responde…";
            } else {
                scheduleVoiceRecognition();
            }
        }
    };
} else {
    voiceButton.disabled = true;
    voiceButton.title = "El reconocimiento de voz no está disponible en este navegador.";
    voiceConversationButton.disabled = true;
    voiceConversationButton.title = "El reconocimiento de voz no está disponible en este navegador.";
}

function finishDictation(submitQuestion) {
    const transcript = input.value.trim();
    dictationActive = false;
    dictationSubmitRequested = false;
    window.clearTimeout(dictationRestartTimer);
    window.clearTimeout(dictationSilenceTimer);
    dictationRestartTimer = null;
    dictationSilenceTimer = null;
    if (recognition) {
        recognition.continuous = false;
        recognition.interimResults = false;
        if (isListening) recognition.stop();
    }
    voiceButton.classList.remove("recording");
    voiceButton.setAttribute("aria-label", "Dictar pregunta por voz");
    voiceButton.querySelector("span").textContent = "Dictar";
    if (submitQuestion && transcript.length >= 2) {
        statusLabel.textContent = "Pregunta reconocida. Buscando respuesta…";
        statusLabel.className = "";
        window.setTimeout(() => form.requestSubmit(), 0);
    } else if (submitQuestion) {
        statusLabel.textContent = "No alcancé a reconocer palabras. Puedes intentarlo de nuevo o escribir tu pregunta.";
        statusLabel.className = "error";
    } else {
        statusLabel.textContent = "Dictado pausado. El texto reconocido se conserva para que puedas editarlo.";
        statusLabel.className = "";
    }
}

function scheduleVoiceRecognition() {
    window.clearTimeout(voiceRestartTimer);
    if (!voiceConversationActive || voiceTurnPending || sendButton.disabled || isListening || !recognition) return;
    voiceRestartTimer = window.setTimeout(() => {
        if (!voiceConversationActive || voiceTurnPending || sendButton.disabled || isListening) return;
        recognitionMode = "conversation";
        recognition.continuous = true;
        recognition.interimResults = true;
        try {
            recognition.start();
        } catch {
            stopVoiceConversation();
            statusLabel.textContent = "No se pudo reactivar el micrófono. Inicia de nuevo la conversación por voz.";
            statusLabel.className = "error";
        }
    }, 350);
}

function resumeVoiceConversation() {
    if (!voiceConversationActive) return;
    voiceTurnPending = false;
    statusLabel.textContent = "Lobo terminó de responder. Puedes hablar de nuevo.";
    statusLabel.className = "";
    voiceConversationButton.querySelector("span").textContent = "Conectando micrófono…";
    scheduleVoiceRecognition();
}

function stopVoiceConversation({ cancelSpeech = false } = {}) {
    voiceConversationActive = false;
    voiceTurnPending = false;
    recognitionMode = "dictation";
    if (recognition) {
        recognition.continuous = false;
        recognition.interimResults = false;
    }
    window.clearTimeout(voiceTranscriptTimer);
    window.clearTimeout(voiceRestartTimer);
    if (recognition && isListening) recognition.stop();
    voiceConversationButton.classList.remove("recording", "conversation-active");
    voiceConversationButton.setAttribute("aria-pressed", "false");
    voiceConversationButton.setAttribute("aria-label", "Iniciar conversación por voz");
    voiceConversationButton.querySelector("span").textContent = "Conversar";
    voiceButton.disabled = false;
    if (cancelSpeech) stopSpeech();
}

voiceConversationButton.addEventListener("click", () => {
    if (!recognition) {
        statusLabel.textContent = "Abre el kiosko en Edge y permite el acceso al micrófono.";
        statusLabel.className = "error";
        return;
    }
    if (voiceConversationActive) {
        stopVoiceConversation({ cancelSpeech: true });
        statusLabel.textContent = "Conversación por voz finalizada.";
        return;
    }
    prepareSpeechAudio();
    voiceConversationActive = true;
    voiceTurnPending = false;
    recognitionMode = "conversation";
    recognition.continuous = true;
    recognition.interimResults = true;
    voiceConversationButton.classList.add("conversation-active");
    voiceConversationButton.setAttribute("aria-pressed", "true");
    voiceConversationButton.setAttribute("aria-label", "Finalizar conversación por voz");
    voiceConversationButton.querySelector("span").textContent = "Iniciando…";
    voiceButton.disabled = true;
    statusLabel.textContent = "Conectando el micrófono…";
    statusLabel.className = "";
    try {
        recognition.start();
    } catch {
        stopVoiceConversation();
        statusLabel.textContent = "No se pudo iniciar el micrófono. Intenta de nuevo.";
        statusLabel.className = "error";
    }
});

voiceButton.addEventListener("click", () => {
    if (!recognition) {
        statusLabel.textContent = "Abre el kiosko en Edge o Chrome y permite el micrófono.";
        statusLabel.className = "error";
        return;
    }
    if (dictationActive) {
        dictationSubmitRequested = true;
        if (isListening) recognition.stop();
        else finishDictation(true);
    } else {
        dictationBaseText = input.value.trim();
        dictationFinalText = "";
        dictationStartedAt = performance.now();
        dictationActive = true;
        dictationSubmitRequested = false;
        recognitionMode = "dictation";
        recognition.continuous = true;
        recognition.interimResults = true;
        try {
            recognition.start();
        } catch {
            dictationActive = false;
            statusLabel.textContent = "El micrófono ya está iniciando. Espera un momento e intenta de nuevo.";
            statusLabel.className = "error";
        }
    }
});

input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    if (!sendButton.disabled && input.value.trim()) form.requestSubmit();
});

async function playGeminiSpeechStream(text, generation) {
    prepareSpeechAudio();
    if (!speechAudioContext) throw new Error("El navegador no admite audio en streaming.");
    if (speechAudioContext.state !== "running") {
        await speechAudioContext.resume();
    }
    if (speechAudioContext.state !== "running") {
        throw new Error("El navegador no habilitó la reproducción de audio.");
    }
    const controller = new AbortController();
    speechRequestController = controller;
    const response = await fetch("/api/v1/voz/sintetizar/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: text }),
        signal: controller.signal,
    });
    if (!response.ok || !response.body) throw new Error("No se pudo iniciar el audio en streaming.");

    const reader = response.body.getReader();
    speechStreamReader = reader;
    let carry = new Uint8Array(0);
    let scheduled = 0;
    const sampleRate = 24000;
    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            if (generation !== speechGeneration) {
                await reader.cancel();
                break;
            }
            if (!value?.length) continue;
            const bytes = new Uint8Array(carry.length + value.length);
            bytes.set(carry);
            bytes.set(value, carry.length);
            const usableLength = bytes.length - (bytes.length % 2);
            carry = usableLength < bytes.length ? bytes.slice(usableLength) : new Uint8Array(0);
            if (!usableLength) continue;

            const frameCount = usableLength / 2;
            const buffer = speechAudioContext.createBuffer(1, frameCount, sampleRate);
            const samples = buffer.getChannelData(0);
            const view = new DataView(bytes.buffer, bytes.byteOffset, usableLength);
            for (let index = 0; index < frameCount; index++) {
                samples[index] = view.getInt16(index * 2, true) / 32768;
            }
            const source = speechAudioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(speechAudioContext.destination);
            const startAt = Math.max(speechAudioContext.currentTime + 0.04, speechScheduleEnd);
            source.start(startAt);
            speechScheduleEnd = startAt + buffer.duration;
            speechAudioSources.push(source);
            speechStreamStarted = true;
            source.onended = () => {
                speechAudioSources = speechAudioSources.filter((item) => item !== source);
                if (!speechAudioSources.length && statusLabel.textContent === "Lobo está hablando…") {
                    statusLabel.textContent = "";
                }
            };
            scheduled++;
            if (scheduled === 1) {
                statusLabel.textContent = "Lobo está hablando…";
                statusLabel.className = "";
                setAvatarSpeaking(true);
            }
        }
    } finally {
        if (speechStreamReader === reader) speechStreamReader = null;
        if (speechRequestController === controller) speechRequestController = null;
        reader.releaseLock();
    }
    if (generation !== speechGeneration) return 0;
    if (scheduled) {
        const remainingMs = Math.max(0, speechScheduleEnd - speechAudioContext.currentTime) * 1000;
        if (remainingMs > 0) await new Promise((resolve) => window.setTimeout(resolve, remainingMs + 40));
    }
    setAvatarSpeaking(false);
    return scheduled;
}

function speakResponse(text, animation = "Hablar") {
    lastAssistantResponse = String(text || "").trim() || lastAssistantResponse;
    stopSpeech();
    const generation = speechGeneration;
    playAvatarAnimation(animation, { loop: shouldLoopAvatarAnimation(animation) });
    if (animation !== "Hablar" && animation !== "Explicar" && animation !== "Idle") {
        // Deja que se vea el gesto propio de la ficha y luego acompaña la voz
        // con Hablar mientras dura la respuesta.
        greetingGestureTimer = window.setTimeout(() => {
            greetingGestureTimer = null;
            if (generation === speechGeneration && avatarSpeaking && !avatarSpeaking.hidden) {
                playAvatarAnimation("Hablar", { loop: true });
            }
        }, Math.ceil((avatarClipDurations[animation] || 2.9) * 1000) + 80);
    }
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") {
        statusLabel.textContent = "La voz no está disponible en este navegador. La respuesta sigue visible.";
        statusLabel.className = "error";
        return Promise.resolve();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-MX";
    utterance.rate = 1.04;
    utterance.pitch = 1.08;
    utterance.voice = kioskSpeechVoice || selectKioskSpeechVoice();

    return new Promise((resolve) => {
        const finish = (error = null) => {
            if (generation === speechGeneration) {
                setAvatarSpeaking(false);
                stopAvatarMotion();
                statusLabel.textContent = error
                    ? "No se pudo reproducir la voz de Lobo. La respuesta sigue visible."
                    : "";
                statusLabel.className = error ? "error" : "";
            }
            resolve();
        };
        utterance.onstart = () => {
            if (generation !== speechGeneration) return;
            statusLabel.textContent = "Lobo está hablando…";
            statusLabel.className = "";
            setAvatarSpeaking(true);
            if (voiceCaption && voiceCaptionText) {
                voiceCaptionText.textContent = text;
                voiceCaptionText.hidden = !subtitlesEnabled;
                voiceCaption.classList.toggle("subtitles-off", !subtitlesEnabled);
                voiceCaption.hidden = false;
            }
        };
        utterance.onend = () => finish();
        utterance.onerror = (event) => finish(!["canceled", "interrupted"].includes(event.error));
        try {
            window.speechSynthesis.speak(utterance);
        } catch {
            finish(true);
        }
    });
}

function speakKioskReply(text, animation, resumeListening) {
    const speech = speakResponse(text, animation);
    if (resumeListening) void speech.finally(resumeVoiceConversation);
    return speech;
}

function parseGoogleMapsUrl(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    const clean = value.trim().replace(/[),.;!?]+$/, "");
    try {
        const url = new URL(clean);
        const host = url.hostname.toLowerCase();
        const googleDomain = /^(www\.)?google\.(com|com\.[a-z]{2}|[a-z]{2,3})$/.test(host);
        const isGoogleMapsHost = host === "maps.app.goo.gl"
            || host === "maps.google.com"
            || (host === "goo.gl" && url.pathname.startsWith("/maps"))
            || (googleDomain && url.pathname.startsWith("/maps"));
        return isGoogleMapsHost ? { url, raw: clean } : null;
    } catch {
        return null;
    }
}

function findGoogleMapsUrl(text) {
    const candidates = text.match(/https?:\/\/[^\s<>"']+/gi) || [];
    for (const candidate of candidates) {
        const match = parseGoogleMapsUrl(candidate);
        if (match) return match;
    }
    return null;
}

function parseYouTubeUrl(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    const clean = value.trim().replace(/[),.;!?]+$/, "");
    try {
        const url = new URL(clean);
        const host = url.hostname.toLowerCase();
        if (!new Set(["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"]).has(host)) return null;
        const pathParts = url.pathname.split("/").filter(Boolean);
        let videoId = "";
        if (host === "youtu.be") videoId = pathParts[0] || "";
        else if (url.pathname === "/watch") videoId = url.searchParams.get("v") || "";
        else if (["embed", "shorts", "live", "v"].includes(pathParts[0])) videoId = pathParts[1] || "";
        if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) return null;
        return {
            raw: clean,
            url,
            embedUrl: `https://www.youtube-nocookie.com/embed/${videoId}?rel=0`,
        };
    } catch {
        return null;
    }
}

function findYouTubeUrl(text) {
    const candidates = text.match(/https?:\/\/[^\s<>"']+/gi) || [];
    for (const candidate of candidates) {
        const video = parseYouTubeUrl(candidate);
        if (video) return video;
    }
    return null;
}

function mapsLocation(url) {
    const placeMatch = url.pathname.match(/\/maps\/place\/([^/]+)/i);
    const coordinateMatch = url.href.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?),(\d+(?:\.\d+)?)z/i);
    let placeName = "";
    if (placeMatch) {
        try { placeName = decodeURIComponent(placeMatch[1].replaceAll("+", " ")); } catch { placeName = placeMatch[1]; }
    }
    const location = (url.searchParams.get("q")
        || url.searchParams.get("query")
        || url.searchParams.get("ll")
        || url.searchParams.get("destination")
        || placeName
        || (coordinateMatch ? `${coordinateMatch[1]},${coordinateMatch[2]}` : "")
        || "Universidad Politécnica del Valle de Toluca").slice(0, 500);
    const zoom = coordinateMatch ? Math.round(Number(coordinateMatch[3])) : 16;
    return { location, zoom: Math.min(21, Math.max(3, zoom)) };
}

function appendMapPreview(article, mapUrl) {
    if (!mapUrl) return;
    const { location, zoom } = mapsLocation(mapUrl.url);
    const card = document.createElement("section");
    card.className = "map-preview";
    card.setAttribute("aria-label", "Mapa de ubicación de la UPVT");
    const heading = document.createElement("h3");
    heading.textContent = "Ubicación en Google Maps";
    const frame = document.createElement("iframe");
    frame.title = "Mapa de Google Maps con la ubicación de la UPVT";
    frame.loading = "lazy";
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    frame.allowFullscreen = true;
    frame.src = `https://www.google.com/maps?q=${encodeURIComponent(location)}&z=${zoom}&output=embed`;
    const actions = document.createElement("div");
    actions.className = "map-preview-actions";
    const open = document.createElement("a");
    open.href = mapUrl.url.href;
    open.target = "_blank";
    open.rel = "noopener noreferrer";
    open.textContent = "Abrir en Google Maps";
    const directions = document.createElement("a");
    directions.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(location)}`;
    directions.target = "_blank";
    directions.rel = "noopener noreferrer";
    directions.textContent = "Cómo llegar";
    actions.append(open, directions);
    card.append(heading, frame, actions);
    article.append(card);
}

function appendVideoPreview(article, video) {
    if (!video) return;
    const card = document.createElement("section");
    card.className = "video-preview";
    card.setAttribute("aria-label", "Video institucional de YouTube");
    const heading = document.createElement("h3");
    heading.textContent = "Video institucional";
    const frame = document.createElement("div");
    frame.className = "video-frame";
    const player = document.createElement("iframe");
    player.src = video.embedUrl;
    player.title = "Video institucional de la UPVT";
    player.loading = "lazy";
    player.referrerPolicy = "strict-origin-when-cross-origin";
    player.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    player.allowFullscreen = true;
    frame.append(player);
    const actions = document.createElement("div");
    actions.className = "video-preview-actions";
    const open = document.createElement("a");
    open.href = video.url.href;
    open.target = "_blank";
    open.rel = "noopener noreferrer";
    open.textContent = "Abrir video en YouTube";
    actions.append(open);
    card.append(heading, frame, actions);
    article.append(card);
}

function addMessage(text, kind, source = null, mapUrlOverride = null, videoUrlOverride = null) {
    const article = document.createElement("article");
    article.className = `message ${kind}-message`;
    const mapUrl = kind === "assistant" ? parseGoogleMapsUrl(mapUrlOverride) || findGoogleMapsUrl(text) : null;
    const video = kind === "assistant" ? parseYouTubeUrl(videoUrlOverride) || findYouTubeUrl(text) : null;
    const paragraph = document.createElement("p");
    let visibleText = text;
    if (mapUrl) visibleText = visibleText.replace(mapUrl.raw, "");
    if (video) visibleText = visibleText.replace(video.raw, "");
    paragraph.textContent = visibleText.replace(/[ \t]+([.,;!?])/g, "$1").trim();
    if (kind === "assistant" && paragraph.textContent) {
        lastAssistantResponse = paragraph.textContent;
        if (repeatResponseButton) repeatResponseButton.disabled = false;
    }
    if (!paragraph.textContent) paragraph.hidden = true;
    article.append(paragraph);
    if (kind === "assistant" && paragraph.textContent) {
        const listen = document.createElement("button");
        listen.type = "button";
        listen.className = "message-speak";
        listen.dataset.speak = "true";
        listen.textContent = "▶ Escuchar";
        listen.setAttribute("aria-label", "Escuchar esta respuesta de Lobo");
        article.append(listen);
    }
    appendMapPreview(article, mapUrl);
    appendVideoPreview(article, video);
    const sources = Array.isArray(source) ? source : source?.url && source?.name ? [source] : [];
    sources.forEach((documentItem) => {
        const citation = document.createElement("div");
        citation.className = "message-source";
        const documentName = documentItem.nombre_archivo || documentItem.name || "Archivo institucional";
        const isImage = String(documentItem.mime_type || "").toLowerCase().startsWith("image/")
            || /\.(png|jpe?g|webp)$/i.test(documentName)
            || /\.(png|jpe?g|webp)(?:[?#].*)?$/i.test(documentItem.url || "");
        if (isImage) {
            const imagePreview = document.createElement("img");
            imagePreview.className = "chat-image-preview";
            imagePreview.src = documentItem.url;
            imagePreview.alt = documentName;
            imagePreview.loading = "lazy";
            article.append(imagePreview);
        }
        const label = document.createElement("span");
        label.textContent = `Archivo relacionado: ${documentName}`;
        const preview = document.createElement("button");
        preview.type = "button";
        preview.textContent = "Vista previa";
        preview.dataset.previewUrl = documentItem.url;
        preview.dataset.previewTitle = documentName;
        const open = document.createElement("a");
        open.href = documentItem.url;
        open.target = "_blank";
        open.rel = "noopener";
        open.textContent = "Abrir archivo";
        citation.append(label, preview, open);
        article.append(citation);
    });
    messages.append(article);
    messages.scrollTop = messages.scrollHeight;
}

messages.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-speak]");
    if (!button) return;
    const text = button.closest(".message")?.querySelector("p")?.textContent?.trim();
    if (text) void speakResponse(text, "Hablar");
});

async function checkConnection() {
    const label = document.querySelector("#connection-label");
    const dot = document.querySelector(".status-dot");
    try {
        const response = await fetch("/health", { cache: "no-store", signal: AbortSignal.timeout(4000) });
        if (!response.ok) throw new Error("offline");
        const state = await response.json();
        label.textContent = state.mysql === "conectado" ? "Servicio disponible" : "Servicio limitado";
        dot.classList.remove("online", "offline");
        dot.classList.add(state.mysql === "conectado" ? "online" : "offline");
    } catch {
        label.textContent = "Sin conexión con el servicio";
        dot.classList.remove("online");
        dot.classList.add("offline");
    }
}

const previewDialog = document.querySelector("#document-preview");
const previewFrame = document.querySelector("#document-preview-frame");
const previewLink = document.querySelector("#document-preview-open");
function openDocumentPreview(url, title) {
    if (typeof previewDialog.showModal !== "function") {
        window.open(url, "_blank", "noopener");
        return;
    }
    document.querySelector("#document-preview-title").textContent = title;
    previewLink.href = url;
    previewFrame.src = url;
    previewDialog.showModal();
}

document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-preview-url]");
    if (!button) return;
    openDocumentPreview(button.dataset.previewUrl, button.dataset.previewTitle);
});
document.querySelector("#close-document-preview").addEventListener("click", () => previewDialog.close());
previewDialog.addEventListener("click", (event) => {
    if (event.target === previewDialog) previewDialog.close();
});
previewDialog.addEventListener("close", () => {
    previewFrame.src = "about:blank";
});

function renderAnnouncement() {
    if (!announcements.length) return;
    const item = announcements[announcementIndex];
    document.querySelector("#announcement-category").textContent = item.categoria || "Aviso institucional";
    document.querySelector("#announcement-title").textContent = item.titulo;
    document.querySelector("#announcement-copy").textContent = item.contenido;
    document.querySelector("#announcement-position").textContent = `${announcementIndex + 1} / ${announcements.length}`;
}

function moveAnnouncement(offset) {
    if (announcements.length < 2) return;
    announcementIndex = (announcementIndex + offset + announcements.length) % announcements.length;
    renderAnnouncement();
}

function setAnnouncementPaused(paused) {
    announcementPaused = paused;
    const button = document.querySelector("#announcement-rotation");
    button.textContent = paused ? "▶" : "Ⅱ";
    button.setAttribute("aria-label", paused ? "Reanudar rotación de avisos" : "Pausar rotación de avisos");
    if (announcementTimer) window.clearInterval(announcementTimer);
    announcementTimer = null;
    if (!paused && announcements.length > 1) {
        announcementTimer = window.setInterval(() => moveAnnouncement(1), 8000);
    }
}

async function loadAnnouncements() {
    const carousel = document.querySelector("#announcements");
    try {
        const response = await fetch("/api/v1/informacion?categoria=Avisos");
        if (!response.ok) throw new Error("No se pudieron cargar los avisos.");
        announcements = await response.json();
        if (!announcements.length) return;
        carousel.hidden = false;
        renderAnnouncement();
        const hasMultiple = announcements.length > 1;
        document.querySelector("#announcement-previous").hidden = !hasMultiple;
        document.querySelector("#announcement-next").hidden = !hasMultiple;
        document.querySelector("#announcement-rotation").hidden = !hasMultiple;
        if (hasMultiple) setAnnouncementPaused(false);
    } catch {
        carousel.hidden = true;
    }
}

document.querySelector("#announcement-previous").addEventListener("click", () => moveAnnouncement(-1));
document.querySelector("#announcement-next").addEventListener("click", () => moveAnnouncement(1));
document.querySelector("#announcement-rotation").addEventListener("click", () => {
    announcementUserPaused = !announcementUserPaused;
    setAnnouncementPaused(announcementUserPaused);
});
document.querySelector("#announcements").addEventListener("mouseenter", () => setAnnouncementPaused(true));
document.querySelector("#announcements").addEventListener("mouseleave", () => setAnnouncementPaused(announcementUserPaused));
document.querySelector("#announcements").addEventListener("focusin", () => setAnnouncementPaused(true));
document.querySelector("#announcements").addEventListener("focusout", (event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) setAnnouncementPaused(announcementUserPaused);
});
document.addEventListener("visibilitychange", () => {
    setAnnouncementPaused(document.hidden || announcementUserPaused);
    if (document.hidden) {
        if (voiceConversationActive) stopVoiceConversation({ cancelSpeech: true });
        else stopSpeech();
    }
});
window.addEventListener("pagehide", () => {
    if (voiceConversationActive) stopVoiceConversation({ cancelSpeech: true });
    else stopSpeech();
});

document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", () => {
        input.value = button.dataset.question;
        input.focus();
    });
});

document.querySelector("#new-chat").addEventListener("click", () => {
    if (voiceConversationActive) stopVoiceConversation({ cancelSpeech: true });
    if (isListening) recognition.stop();
    stopSpeech();
    messages.replaceChildren();
    addMessage("Hola, soy el asistente de la UPVT. Escribe tu pregunta y buscaré la información disponible.", "assistant");
    statusLabel.textContent = "";
    statusLabel.className = "";
    input.value = "";
    input.focus();
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (question.length < 2 || sendButton.disabled) return;
    const resumeVoiceAfterReply = voiceConversationActive;
    if (resumeVoiceAfterReply) {
        voiceTurnPending = true;
        window.clearTimeout(voiceTranscriptTimer);
        if (isListening) recognition.stop();
    }
    stopSpeech();
    prepareSpeechAudio();

    const context = Array.from(messages.querySelectorAll(".message"))
        .slice(-6)
        .map((message) => ({
            role: message.classList.contains("user-message") ? "user" : "assistant",
            content: message.querySelector("p")?.textContent?.trim() || "",
        }))
        .filter((message) => message.content);
    addMessage(question, "user");
    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;
    statusLabel.textContent = "Buscando respuesta...";
    statusLabel.className = "";
    playAvatarAnimation("Pensar");

    try {
        const localReply = casualKioskResponse(question);
        let payload;
        if (localReply) {
            payload = { respuesta: localReply, animacion: "greeting", emocion: "happy" };
            // Persist greetings when the API is available, without making the
            // visitor wait for MySQL or replacing the immediate spoken reply.
            void fetch("/api/v1/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mensaje: question, contexto: context, request_id: newRequestId() }),
                signal: AbortSignal.timeout(4000),
            }).catch(() => {});
        } else {
            payload = await requestChat(question, context);
        }
        const relatedDocuments = payload.documentos?.length ? payload.documentos : payload.urlDocumento ? [{
            name: payload.fuenteDocumental || "Documento institucional",
            url: payload.urlDocumento,
        }] : null;
        addMessage(payload.respuesta, "assistant", relatedDocuments, payload.mapaUrl, payload.videoUrl);
        statusLabel.textContent = "";
        void speakKioskReply(payload.respuesta, animationForReply(payload, question), resumeVoiceAfterReply);
    } catch (error) {
        const friendlyError = "¡Con gusto te ayudo! En este momento no puedo consultar la información. Intenta de nuevo en unos segundos.";
        addMessage(friendlyError, "assistant");
        void speakResponse(friendlyError, "Hablar").finally(() => {
            if (resumeVoiceAfterReply) resumeVoiceConversation();
        });
        statusLabel.textContent = "No se pudo consultar la información. Intenta de nuevo.";
        statusLabel.className = "error";
    } finally {
        input.disabled = false;
        sendButton.disabled = false;
        if (!voiceConversationActive) input.focus();
    }
});

checkConnection();
window.setInterval(checkConnection, 10000);
loadAnnouncements();

window.LoboKiosk = {
    enableAudio() { prepareSpeechAudio(); },
    welcomeVisitor() {
        if (sendButton.disabled) return false;
        const greeting = "¡Hola! Qué gusto que estés aquí. Soy Lobo, tu asistente de la UPVT. Puedes preguntarme sobre carreras, servicios o la universidad. ¿En qué te ayudo?";
        addMessage(greeting, "assistant");
        statusLabel.textContent = "";
        void speakKioskReply(greeting, "Saludo", false);
        void fetch("/api/v1/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mensaje: "hola", contexto: [], request_id: newRequestId() }),
            signal: AbortSignal.timeout(4000),
        }).catch(() => {});
        return true;
    },
    async respondToCamera(text, animation) {
        if (sendButton.disabled) return false;
        sendButton.disabled = true;
        input.disabled = true;
        statusLabel.textContent = "Registrando la interacción…";
        try {
            const payload = await requestChat(text, []);
            addMessage(payload.respuesta, "assistant");
            statusLabel.textContent = "";
            const gestureAnimation = ["Saludo", "Celebrar"].includes(animation) ? animation : null;
            void speakKioskReply(payload.respuesta, gestureAnimation || animationForReply(payload, text));
            return true;
        } catch {
            statusLabel.textContent = "No se pudo conectar. Puedes escribir tu pregunta y volver a intentarlo.";
            statusLabel.className = "error";
            return false;
        } finally {
            sendButton.disabled = false;
            input.disabled = false;
            if (!voiceConversationActive) input.focus();
        }
    },
    visitorLeft() {
        if (voiceConversationActive) stopVoiceConversation({ cancelSpeech: true });
        else stopSpeech();
        statusLabel.textContent = "";
    },
    get isBusy() { return sendButton.disabled; },
};
