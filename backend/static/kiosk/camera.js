const toggle = document.querySelector("#camera-toggle");
const status = document.querySelector("#camera-status");
const video = document.querySelector("#presence-camera");

const MEDIAPIPE_VERSION = "1.2.3";
const VISION_WASM = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/wasm`;
const FACE_MODEL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";
const GESTURE_MODEL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";

let cameraStream = null;
let faceDetector = null;
let gestureRecognizer = null;
let animationFrame = 0;
let lastInferenceAt = 0;
let detectedFaceFrames = 0;
let missingFaceSince = 0;
let visitorPresent = false;
let greetingDelivered = false;
let lastFaceSearchStatusAt = 0;
let lastGestureAt = 0;
let lastWristX = null;
let lastDirection = 0;
let directionChanges = 0;
let waveStartedAt = 0;
let handWindow = [];

function setCameraState(enabled, label) {
    toggle.setAttribute("aria-pressed", String(enabled));
    toggle.querySelector("span").textContent = enabled ? "Desactivar cámara" : "Activar cámara";
    toggle.classList.toggle("is-active", enabled);
    status.textContent = label;
}

async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Este navegador no permite usar la cámara en esta dirección. Abre el kiosko en localhost o HTTPS.");
    }
    // Solo se solicita video; no se activa ni se captura el micrófono.
    cameraStream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "user" }, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15, max: 24 } },
    });
    video.srcObject = cameraStream;
    await video.play();
    setCameraState(true, "Cargando detección local…");

    const visionModuleUrl = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MEDIAPIPE_VERSION}/+esm`;
    const { FilesetResolver, FaceDetector, GestureRecognizer } = await import(visionModuleUrl);
    const vision = await FilesetResolver.forVisionTasks(VISION_WASM);
    faceDetector = await FaceDetector.createFromOptions(vision, {
        baseOptions: { modelAssetPath: FACE_MODEL, delegate: "CPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.5,
    });

    lastInferenceAt = 0;
    detectedFaceFrames = 0;
    missingFaceSince = 0;
    visitorPresent = false;
    greetingDelivered = false;
    lastFaceSearchStatusAt = 0;
    setCameraState(true, "Cámara activa · buscando tu rostro…");
    animationFrame = requestAnimationFrame(detectLoop);

    // La bienvenida no debe depender de que el modelo de gestos termine de
    // descargarse. Si ese modelo falla, la detección de rostro sigue activa.
    void GestureRecognizer.createFromOptions(vision, {
        baseOptions: { modelAssetPath: GESTURE_MODEL, delegate: "CPU" },
        runningMode: "VIDEO",
        numHands: 1,
        minHandDetectionConfidence: 0.65,
        minHandPresenceConfidence: 0.55,
        minTrackingConfidence: 0.55,
    }).then((recognizer) => {
        if (!cameraStream?.active) {
            recognizer.close();
            return;
        }
        gestureRecognizer = recognizer;
    }).catch(() => {
        // El saludo por presencia continúa; solo se desactivan los gestos de mano.
        if (cameraStream?.active) setCameraState(true, "Presencia activa · gestos de mano no disponibles");
    });
}

function resetWave() {
    handWindow = [];
    lastWristX = null;
    lastDirection = 0;
    directionChanges = 0;
    waveStartedAt = 0;
}

function triggerGesture(animation, message) {
    const now = performance.now();
    if (!visitorPresent || now - lastGestureAt < 6000 || window.LoboKiosk?.isBusy) return;
    if (window.LoboKiosk?.respondToCamera(message, animation)) lastGestureAt = now;
}

function handleHandGesture(result, now) {
    const category = result.gestures?.[0]?.[0]?.categoryName || "";
    const confidence = result.gestures?.[0]?.[0]?.score || 0;
    const wrist = result.landmarks?.[0]?.[0];

    if (category === "Thumb_Up" && confidence >= 0.72) {
        resetWave();
        triggerGesture("Celebrar", "¡Buen gesto! Vamos a celebrar.");
        return;
    }

    if (category !== "Open_Palm" || confidence < 0.68 || !wrist) {
        resetWave();
        return;
    }

    if (!waveStartedAt || now - waveStartedAt > 1800) {
        resetWave();
        waveStartedAt = now;
    }
    const x = wrist.x;
    if (lastWristX !== null) {
        const delta = x - lastWristX;
        const direction = Math.abs(delta) > 0.025 ? Math.sign(delta) : lastDirection;
        if (direction && lastDirection && direction !== lastDirection) directionChanges++;
        if (direction) lastDirection = direction;
    }
    lastWristX = x;
    handWindow.push(x);
    if (handWindow.length > 9) handWindow.shift();
    const travel = handWindow.length > 1 ? Math.max(...handWindow) - Math.min(...handWindow) : 0;
    if (handWindow.length >= 6 && travel > 0.13 && directionChanges >= 2) {
        resetWave();
        triggerGesture("Saludo", "El visitante saludó con la mano.");
    }
}

function detectLoop(now) {
    if (!cameraStream?.active || document.hidden) return;
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0 && video.videoHeight > 0 && now - lastInferenceAt >= 350) {
        lastInferenceAt = now;
        try {
            const timestamp = Math.round(now);
            const faceResult = faceDetector.detectForVideo(video, timestamp);
            const hasFace = (faceResult.detections || []).some((item) => item.categories?.[0]?.score >= 0.5);
            if (hasFace) {
                detectedFaceFrames++;
                missingFaceSince = 0;
                if (!visitorPresent && detectedFaceFrames >= 3) {
                    visitorPresent = true;
                    greetingDelivered = false;
                    setCameraState(true, "Visitante detectado · listo para interactuar");
                }
            } else {
                detectedFaceFrames = 0;
                if (!visitorPresent && now - lastFaceSearchStatusAt > 1800) {
                    lastFaceSearchStatusAt = now;
                    setCameraState(true, "Cámara activa · centra tu rostro frente a la pantalla");
                }
                if (visitorPresent) {
                    missingFaceSince ||= now;
                    if (now - missingFaceSince > 4000) {
                        visitorPresent = false;
                        greetingDelivered = false;
                        setCameraState(true, "Cámara activa · esperando visitante");
                        resetWave();
                        window.LoboKiosk?.visitorLeft();
                    }
                }
            }

            if (visitorPresent) {
                if (!greetingDelivered && !window.LoboKiosk?.isBusy) {
                    greetingDelivered = window.LoboKiosk?.welcomeVisitor() === true;
                }
                if (gestureRecognizer) {
                    const handResult = gestureRecognizer.recognizeForVideo(video, timestamp);
                    handleHandGesture(handResult, now);
                }
            }
        } catch {
            setCameraState(true, "No puedo analizar la cámara. Desactívala y vuelve a activarla.");
        }
    }
    animationFrame = requestAnimationFrame(detectLoop);
}

function stopCamera(label = "Cámara apagada") {
    cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    for (const track of cameraStream?.getTracks() || []) track.stop();
    cameraStream = null;
    video.srcObject = null;
    faceDetector?.close();
    gestureRecognizer?.close();
    faceDetector = null;
    gestureRecognizer = null;
    detectedFaceFrames = 0;
    visitorPresent = false;
    greetingDelivered = false;
    resetWave();
    window.LoboKiosk?.visitorLeft();
    setCameraState(false, label);
}

toggle.addEventListener("click", async () => {
    if (cameraStream) {
        stopCamera();
        return;
    }
    // Aprovecha el clic del usuario para habilitar la reproducción de audio del navegador.
    window.LoboKiosk?.enableAudio();
    toggle.disabled = true;
    setCameraState(false, "Solicitando permiso de cámara…");
    try {
        await startCamera();
    } catch (error) {
        stopCamera(error.name === "NotAllowedError"
            ? "Permite el acceso a la cámara en el navegador y vuelve a intentarlo."
            : error.message || "No se pudo iniciar la cámara.");
    } finally {
        toggle.disabled = false;
    }
});

document.addEventListener("visibilitychange", () => {
    if (document.hidden && cameraStream) stopCamera("Cámara apagada al salir del kiosko");
});
window.addEventListener("pagehide", () => stopCamera());
