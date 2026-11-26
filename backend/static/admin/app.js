const API = "/api/v1";
const accessScreen = document.querySelector("#access-screen");
const adminScreen = document.querySelector("#admin-screen");
const accessMessage = document.querySelector("#access-message");
const appMessage = document.querySelector("#app-message");
const tokenKey = "lobo_admin_token";
let adminUser = null;
const contentAdminViews = new Set(["summary", "questions", "information", "contact-messages", "history", "metrics", "trash"]);
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let contentRecognition = null;
let activeDictationButton = null;
let activeDictationField = null;
let dictationBaseText = "";
let dictationFinalText = "";
let dictationInterimText = "";
let informationIndexPollTimer = null;
let questionsPage = 1;
let questionsSearchTimer = null;
let healthPollTimer = null;
let requestPollTimer = null;
let contactStreamController = null;
let knownContactMessageIds = null;
let contactReplyAttachments = [];
const maxContactReplyAttachments = 10;
const maxContactReplyBytes = 17 * 1024 * 1024;

function token() {
    return sessionStorage.getItem(tokenKey);
}

function showMessage(element, text, kind = "") {
    element.textContent = text;
    element.className = `message${kind ? ` ${kind}` : ""}`;
}

function initContentDictation() {
    const targets = [
        '#question-form input[name="categoria"]',
        '#question-form input[name="pregunta"]',
        '#question-form input[name="palabras_clave"]',
        '#question-form textarea[name="respuesta"]',
        '#manual-information-form input[name="categoria"]',
        '#manual-information-form input[name="titulo"]',
        '#manual-information-form textarea[name="contenido"]',
        '.draft-fields input[data-field="titulo"]',
        '.draft-fields input[data-field="categoria"]',
        '.draft-fields textarea[data-field="contenido"]',
    ].join(",");
    const status = document.querySelector("#content-voice-status");

    if (!SpeechRecognition) {
        showMessage(status, "El dictado no está disponible en este navegador; puedes escribir normalmente.");
    } else {
        contentRecognition = new SpeechRecognition();
        contentRecognition.lang = "es-MX";
        contentRecognition.continuous = true;
        contentRecognition.interimResults = true;
        contentRecognition.onstart = () => {
            activeDictationButton?.classList.add("recording");
            activeDictationButton?.setAttribute("aria-pressed", "true");
            activeDictationButton?.setAttribute("aria-label", `Detener dictado en ${activeDictationField?.dataset.dictationLabel || "el campo"}`);
            activeDictationButton?.querySelector("span").replaceChildren(document.createTextNode("Detener"));
            showMessage(status, `Escuchando para ${activeDictationField?.dataset.dictationLabel || "el campo"}. Pulsa Detener al terminar.`);
        };
        contentRecognition.onresult = (event) => {
            dictationInterimText = "";
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const text = event.results[index][0]?.transcript?.trim();
                if (!text) continue;
                if (event.results[index].isFinal) dictationFinalText = `${dictationFinalText} ${text}`.trim();
                else dictationInterimText = `${dictationInterimText} ${text}`.trim();
            }
            const separator = dictationBaseText ? (activeDictationField.tagName === "TEXTAREA" ? "\n" : " ") : "";
            activeDictationField.value = `${dictationBaseText}${separator}${[dictationFinalText, dictationInterimText].filter(Boolean).join(" ")}`;
            activeDictationField.dispatchEvent(new Event("input", { bubbles: true }));
        };
        contentRecognition.onerror = (event) => {
            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                showMessage(status, "Permite el acceso al micrófono en el navegador para dictar.", "error");
            } else if (event.error === "no-speech") {
                showMessage(status, "No se detectó voz. Pulsa Dictar e intenta de nuevo.", "error");
            } else if (event.error !== "aborted") {
                showMessage(status, "No se pudo reconocer la voz. Puedes escribir en el campo.", "error");
            }
        };
        contentRecognition.onend = () => {
            const transcript = [dictationFinalText].filter(Boolean).join(" ");
            if (activeDictationField && transcript) {
                const separator = dictationBaseText ? (activeDictationField.tagName === "TEXTAREA" ? "\n" : " ") : "";
                activeDictationField.value = `${dictationBaseText}${separator}${transcript}`;
                activeDictationField.dispatchEvent(new Event("input", { bubbles: true }));
                activeDictationField.dispatchEvent(new Event("change", { bubbles: true }));
                showMessage(status, "Dictado agregado. Revisa el texto antes de guardar.", "success");
            }
            activeDictationButton?.classList.remove("recording");
            activeDictationButton?.setAttribute("aria-pressed", "false");
            activeDictationButton?.setAttribute("aria-label", `Dictar en ${activeDictationField?.dataset.dictationLabel || "el campo"}`);
            if (activeDictationButton) activeDictationButton.querySelector("span").textContent = "Dictar";
            activeDictationButton = null;
            activeDictationField = null;
            dictationInterimText = "";
        };
    }

    function enhanceFields(container) {
        if (!(container instanceof Element || container instanceof Document)) return;
        const fields = [];
        if (container instanceof Element && container.matches(targets)) fields.push(container);
        fields.push(...container.querySelectorAll(targets));
        fields.forEach((field) => {
            if (field.dataset.dictationReady) return;
            field.dataset.dictationReady = "true";
            const label = field.closest("label");
            const labelText = label?.firstChild?.textContent?.trim().replace(/\s+/g, " ") || "el campo";
            field.dataset.dictationLabel = labelText;
            const wrapper = document.createElement("span");
            wrapper.className = "dictation-field";
            const button = document.createElement("button");
            button.className = "dictation-button";
            button.type = "button";
            button.setAttribute("aria-label", `Dictar en ${labelText}`);
            button.setAttribute("aria-pressed", "false");
            button.title = `Dictar en ${labelText}`;
            button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z"/><path d="M19 11a7 7 0 0 1-14 0M12 18v4m-4 0h8"/></svg><span>Dictar</span>';
            field.replaceWith(wrapper);
            wrapper.append(field, button);
            if (!contentRecognition) {
                button.disabled = true;
                button.title = "El reconocimiento de voz no está disponible en este navegador.";
            } else {
                button.addEventListener("click", () => {
                    if (activeDictationButton === button) {
                        contentRecognition.stop();
                        return;
                    }
                    if (activeDictationButton) {
                        showMessage(status, "Detén el dictado actual antes de elegir otro campo.");
                        return;
                    }
                    activeDictationButton = button;
                    activeDictationField = field;
                    dictationBaseText = field.value.trim();
                    dictationFinalText = "";
                    dictationInterimText = "";
                    try {
                        contentRecognition.start();
                    } catch {
                        activeDictationButton = null;
                        activeDictationField = null;
                        showMessage(status, "El micrófono ya está iniciando. Espera un momento e intenta de nuevo.", "error");
                    }
                });
            }
        });
    }

    enhanceFields(document);
    new MutationObserver((records) => {
        records.forEach((record) => record.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) enhanceFields(node);
        }));
    }).observe(document.querySelector("#information-drafts"), { childList: true, subtree: true });
}

async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body) headers.set("Content-Type", "application/json");
    if (token()) headers.set("Authorization", `Bearer ${token()}`);
    const response = await fetch(`${API}${path}`, { ...options, headers });
    if (response.status === 204) return null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const detail = Array.isArray(payload.detail)
            ? payload.detail.map((item) => item.msg).filter(Boolean).join(" ")
            : payload.detail;
        throw new Error(detail || `Error ${response.status}`);
    }
    return payload;
}

function initPasswordVisibility() {
    const eyeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M2.25 12s3.5-6 9.75-6 9.75 6 9.75 6-3.5 6-9.75 6-9.75-6-9.75-6Z"/><circle cx="12" cy="12" r="2.5"/></svg>';
    const hiddenIcon = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m3 3 18 18M10.6 6.2A10.8 10.8 0 0 1 12 6c6.25 0 9.75 6 9.75 6a16 16 0 0 1-2.5 3.1M6.2 6.2C3.65 7.8 2.25 12 2.25 12s3.5 6 9.75 6c.7 0 1.38-.08 2-.22"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';

    document.querySelectorAll(".password-visibility-toggle").forEach((toggle) => {
        if (toggle.dataset.visibilityToggleReady) return;
        toggle.dataset.visibilityToggleReady = "true";
        const input = toggle.closest(".password-field")?.querySelector("input");
        if (!input) return;
        toggle.addEventListener("click", () => {
            const reveal = input.type === "password";
            input.type = reveal ? "text" : "password";
            toggle.setAttribute("aria-label", reveal ? "Ocultar contraseña" : "Mostrar contraseña");
            toggle.setAttribute("aria-pressed", String(reveal));
            toggle.innerHTML = reveal ? eyeIcon : hiddenIcon;
            input.focus();
        });
    });
}

initPasswordVisibility();

function setAccessTab(name) {
    document.querySelector(".access-tabs").classList.remove("hidden");
    document.querySelector("#forgot-password-form").classList.add("hidden");
    document.querySelector("#reset-password-form").classList.add("hidden");
    document.querySelector("#forgot-password-button").classList.toggle("hidden", name !== "login");
    document.querySelectorAll("[data-access-tab]").forEach((button) => {
        const selected = button.dataset.accessTab === name;
        button.classList.toggle("selected", selected);
        button.setAttribute("aria-selected", String(selected));
    });
    document.querySelectorAll("[data-access-form]").forEach((form) => {
        form.classList.toggle("hidden", form.dataset.accessForm !== name);
    });
    showMessage(accessMessage, "");
}

function setView(name) {
    if (adminUser?.rol === "admin_contenido" && !contentAdminViews.has(name)) {
        name = "questions";
    }
    document.querySelectorAll("[data-page]").forEach((section) => {
        section.classList.toggle("hidden", section.dataset.page !== name);
    });
    document.querySelectorAll("[data-view]").forEach((button) => {
        const selected = button.dataset.view === name;
        button.classList.toggle("active", selected);
        if (selected) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });
    showMessage(appMessage, "");
    const load = { summary: loadDashboard, questions: loadQuestions, information: loadInformation, requests: loadRequests, "contact-messages": loadContactMessages, users: loadUsers, history: loadHistory, metrics: loadMetrics, trash: loadTrash }[name];
    load?.().catch((error) => showMessage(appMessage, error.message, "error"));
}

function cell(row, value, className = "") {
    const element = document.createElement("td");
    element.textContent = value ?? "—";
    if (className) element.className = className;
    row.append(element);
    return element;
}

function emptyRow(body, columns, text) {
    body.replaceChildren();
    const row = document.createElement("tr");
    const empty = document.createElement("td");
    empty.colSpan = columns;
    empty.className = "empty-cell";
    empty.textContent = text;
    row.append(empty);
    body.append(row);
}

async function loadDashboard() {
    const data = await api("/admin/dashboard");
    document.querySelector("#metric-faq").textContent = data.respuestas_registradas ?? 0;
    document.querySelector("#metric-attentions").textContent = data.atenciones_totales ?? "—";
    const pendingMetric = document.querySelector("#metric-pending");
    if (pendingMetric) pendingMetric.textContent = data.solicitudes_pendientes ?? "—";
    const list = document.querySelector("#popular-questions");
    list.replaceChildren();
    const questions = data.preguntas_frecuentes || [];
    if (!questions.length) {
        list.textContent = "Todavía no hay consultas registradas.";
        list.classList.add("simple-row");
        return;
    }
    list.classList.remove("simple-row");
    questions.forEach((question) => {
        const row = document.createElement("div");
        row.className = "simple-row";
        const title = document.createElement("span");
        title.textContent = question.pregunta;
        const count = document.createElement("strong");
        count.textContent = question.consultas;
        row.append(title, count);
        list.append(row);
    });
}

async function downloadDashboardReport(event) {
    const button = event.currentTarget;
    button.disabled = true;
    showMessage(appMessage, "Preparando el Excel con gráficas…");
    try {
        const response = await fetch(`${API}/admin/dashboard/reporte.xlsx`, {
            headers: { Authorization: `Bearer ${token()}` },
        });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || `No se pudo generar el reporte (error ${response.status}).`);
        }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = `reporte-resumen-lobo-upvt-${new Date().toISOString().slice(0, 10)}.xlsx`;
        document.body.append(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        showMessage(appMessage, "Reporte Excel descargado con sus gráficas.", "success");
    } catch (error) {
        showMessage(appMessage, error.message, "error");
    } finally {
        button.disabled = false;
    }
}

function actionButton(text, callback, style = "secondary") {
    const button = document.createElement("button");
    button.className = `button ${style}`;
    button.type = "button";
    button.textContent = text;
    const actionTips = {
        "Enviar a papelera": "Retira la pregunta y sus archivos; podrás restaurarlos durante 30 días.",
        Ocultar: "Retira este documento de la lista pública del kiosko.",
        "Eliminar definitivamente": "Borra el archivo del sistema; esta acción no se puede deshacer.",
        Eliminar: "Archiva esta información para que deje de mostrarse en el kiosko.",
    };
    if (actionTips[text]) button.dataset.tooltip = actionTips[text];
    button.addEventListener("click", callback);
    return button;
}

async function loadQuestions() {
    const body = document.querySelector("#questions-body");
    const params = new URLSearchParams({ pagina: String(questionsPage), por_pagina: "25" });
    const search = document.querySelector("#questions-search").value.trim();
    const category = document.querySelector("#questions-category").value;
    if (search) params.set("q", search);
    if (category) params.set("categoria", category);
    const result = await api(`/admin/preguntas/paginadas?${params}`);
    const items = result.items || [];
    const categorySelect = document.querySelector("#questions-category");
    const selectedCategory = categorySelect.value;
    const categoryNames = ["", ...(result.categorias || [])];
    categorySelect.replaceChildren(...categoryNames.map((name, index) => {
        const option = document.createElement("option");
        option.value = index === 0 ? "" : name;
        option.textContent = index === 0 ? "Todas las categorías" : name;
        return option;
    }));
    categorySelect.value = selectedCategory;
    const pages = Math.max(1, result.paginas || 0);
    document.querySelector("#questions-page-summary").textContent = result.total
        ? `Página ${result.pagina} de ${pages} · ${result.total} resultados`
        : "0 resultados";
    document.querySelector("#questions-prev").disabled = result.pagina <= 1;
    document.querySelector("#questions-next").disabled = result.pagina >= pages;
    body.replaceChildren();
    if (!items.length) return emptyRow(body, 6, "No hay respuestas registradas.");
    items.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.pregunta);
        cell(row, item.categoria);
        cell(row, item.animacion || "Hablar");
        cell(row, item.activo ? "Activa" : "Archivada", `status ${item.activo ? "active" : "inactive"}`);
        const documentsCell = document.createElement("td");
        const documents = (item.documentos || []).filter((doc) => doc.activo && !doc.papelera_en);
        if (!documents.length) documentsCell.textContent = "—";
        documents.forEach((documentItem) => {
            const line = document.createElement("div");
            line.className = "row-actions";
            if (item.activo) {
                const link = document.createElement("a");
                link.href = documentItem.url;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = documentItem.nombre_archivo;
                line.append(link);
            } else {
                line.textContent = `${documentItem.nombre_archivo} (pregunta archivada)`;
            }
            line.append(actionButton("Papelera", async () => {
                if (!window.confirm(`¿Mover “${documentItem.nombre_archivo}” a la papelera por 30 días?`)) return;
                try {
                    await api(`/admin/documentos/${documentItem.id}/papelera`, { method: "POST" });
                    showMessage(appMessage, "Archivo enviado a la papelera.", "success");
                    await loadQuestions();
                } catch (error) { showMessage(appMessage, error.message, "error"); }
            }, "secondary"));
            documentsCell.append(line);
        });
        row.append(documentsCell);
        const actions = document.createElement("td");
        const group = document.createElement("div");
        group.className = "row-actions";
        group.append(actionButton("Editar", () => fillQuestionForm(item)));
        if (item.papelera_en == null) group.append(actionButton("Enviar a papelera", () => archiveQuestion(item.id), "secondary"));
        actions.append(group);
        row.append(actions);
        body.append(row);
    });
}

function fillQuestionForm(item) {
    const form = document.querySelector("#question-form");
    const actionStatus = document.querySelector("#question-avatar-action-status");
    actionStatus.textContent = "";
    actionStatus.className = "";
    Object.entries(item).forEach(([key, value]) => {
        if (form.elements[key]) {
            if (form.elements[key].type === "checkbox") form.elements[key].checked = Boolean(value);
            else form.elements[key].value = value ?? "";
        }
    });
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function archiveQuestion(id) {
    if (!window.confirm("¿Enviar esta pregunta y sus archivos a la papelera por 30 días?")) return;
    try {
        await api(`/admin/preguntas/${id}`, { method: "DELETE" });
        showMessage(appMessage, "Pregunta y archivos enviados a la papelera.", "success");
        await loadQuestions();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

async function loadInformation() {
    if (informationIndexPollTimer) {
        window.clearTimeout(informationIndexPollTimer);
        informationIndexPollTimer = null;
    }
    const body = document.querySelector("#information-body");
    const items = await api("/admin/informacion");
    body.replaceChildren();
    if (!items.length) return emptyRow(body, 6, "Todavía no hay información institucional guardada.");
    items.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.titulo);
        cell(row, item.categoria);
        cell(row, item.animacion || "Hablar");
        cell(row, item.activo ? "Activa" : "Archivada", `status ${item.activo ? "active" : "inactive"}`);
        const documentsCell = document.createElement("td");
        const documents = (item.documentos || []).filter((documentItem) => !documentItem.papelera_en);
        if (!documents.length) documentsCell.textContent = "—";
        documents.forEach((documentItem) => {
            const line = document.createElement("div");
            line.className = "row-actions";
            const indexingStatus = document.createElement("small");
            indexingStatus.className = `status ${documentItem.estado_indice === "listo" ? "active" : documentItem.estado_indice === "error" ? "inactive" : "pending"}`;
            indexingStatus.textContent = documentItem.estado_indice === "pendiente"
                ? (documentItem.texto_indexado ? "Listo para buscar; Gemini ampliando índice" : "Gemini preparando índice")
                : documentItem.estado_indice === "error"
                    ? (documentItem.texto_indexado ? "Disponible con texto extraído" : "No se pudo indexar")
                    : "Índice listo para buscar";
            line.append(indexingStatus);
            if (documentItem.activo && item.activo) {
                const link = document.createElement("a");
                link.href = documentItem.url;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = documentItem.nombre_archivo;
                line.append(link, actionButton("Ocultar", async () => {
                    try {
                        await api(`/admin/documentos/${documentItem.id}`, { method: "DELETE" });
                        showMessage(appMessage, "Documento ocultado del kiosko.", "success");
                        await loadInformation();
                    } catch (error) { showMessage(appMessage, error.message, "error"); }
                }));
            } else {
                line.textContent = `${documentItem.nombre_archivo} (archivado)`;
            }
            line.append(actionButton("Mover a papelera", async () => {
                const confirmed = window.confirm(`¿Mover “${documentItem.nombre_archivo}” a la papelera? Podrás restaurarlo durante 30 días.`);
                if (!confirmed) return;
                try {
                    await api(`/admin/documentos/${documentItem.id}/papelera`, { method: "POST" });
                    showMessage(appMessage, "Documento enviado a la papelera.", "success");
                    await loadInformation();
                } catch (error) { showMessage(appMessage, error.message, "error"); }
            }, "secondary"));
            documentsCell.append(line);
        });
        row.append(documentsCell);
        const actionsCell = document.createElement("td");
        const actions = document.createElement("div");
        actions.className = "row-actions";
        actions.append(actionButton("Editar", () => editInformation(item)));
        if (item.activo) {
            actions.append(actionButton("Eliminar", () => archiveInformation(item), "secondary"));
        } else {
            actions.append(
                actionButton("Reactivar", () => setInformationActive(item, true), "primary"),
                actionButton("Mover a papelera", async () => {
                    if (!window.confirm(`¿Mover “${item.titulo}” a la papelera? Podrás restaurarlo durante 30 días.`)) return;
                    try {
                        await api(`/admin/informacion/${item.id}/papelera`, { method: "POST" });
                        showMessage(appMessage, "Información enviada a la papelera junto con sus documentos.", "success");
                        await loadInformation();
                    } catch (error) { showMessage(appMessage, error.message, "error"); }
                }, "secondary"),
            );
        }
        actionsCell.append(actions);
        row.append(actionsCell);
        body.append(row);
    });
    const hasPendingIndex = items.some((item) => (item.documentos || []).some((documentItem) => documentItem.estado_indice === "pendiente"));
    const informationPage = document.querySelector('[data-page="information"]');
    if (hasPendingIndex && informationPage && !informationPage.classList.contains("hidden")) {
        informationIndexPollTimer = window.setTimeout(() => {
            loadInformation().catch((error) => showMessage(appMessage, error.message, "error"));
        }, 3000);
    }
}

function formatTrashDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}

function trashExpiryDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    date.setDate(date.getDate() + 30);
    return date.toLocaleDateString("es-MX", { dateStyle: "medium" });
}

async function loadTrash() {
    const questionsBody = document.querySelector("#trash-questions-body");
    const informationBody = document.querySelector("#trash-information-body");
    const documentsBody = document.querySelector("#trash-documents-body");
    const usersBody = document.querySelector("#trash-users-body");
    const contactMessagesBody = document.querySelector("#trash-contact-messages-body");
    const usersSection = document.querySelector("#trash-users-section");
    const trash = await api("/admin/papelera");
    questionsBody.replaceChildren();
    informationBody.replaceChildren();
    documentsBody.replaceChildren();
    usersBody.replaceChildren();
    contactMessagesBody.replaceChildren();
    usersSection.classList.toggle("hidden", !adminUser?.es_admin_principal);
    if (!trash.preguntas?.length) emptyRow(questionsBody, 5, "No hay preguntas en la papelera.");
    (trash.preguntas || []).forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.pregunta);
        cell(row, item.categoria);
        cell(row, formatTrashDate(item.papelera_en));
        cell(row, trashExpiryDate(item.papelera_en));
        const actions = cell(row, "");
        actions.append(actionButton("Restaurar", async () => {
            try {
                await api(`/admin/preguntas/${item.id}/restaurar`, { method: "POST" });
                showMessage(appMessage, "Pregunta y archivos restaurados.", "success");
                await loadTrash();
            } catch (error) { showMessage(appMessage, error.message, "error"); }
        }, "primary"));
        questionsBody.append(row);
    });
    if (!trash.informacion.length) emptyRow(informationBody, 5, "No hay información institucional en la papelera.");
    trash.informacion.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.titulo);
        cell(row, item.categoria);
        cell(row, formatTrashDate(item.papelera_en));
        cell(row, trashExpiryDate(item.papelera_en));
        const actions = cell(row, "");
        actions.append(actionButton("Restaurar", async () => {
            try {
                await api(`/admin/informacion/${item.id}/restaurar`, { method: "POST" });
                showMessage(appMessage, "Información restaurada. Puedes reactivarla desde Información institucional.", "success");
                await loadTrash();
            } catch (error) { showMessage(appMessage, error.message, "error"); }
        }, "primary"));
        informationBody.append(row);
    });
    if (!trash.documentos.length) emptyRow(documentsBody, 5, "No hay documentos en la papelera.");
    trash.documentos.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.nombre_archivo);
        cell(row, item.informacion_titulo);
        cell(row, formatTrashDate(item.papelera_en));
        cell(row, trashExpiryDate(item.papelera_en));
        const actions = cell(row, "");
        actions.append(actionButton("Restaurar", async () => {
            try {
                await api(`/admin/documentos/${item.id}/restaurar`, { method: "POST" });
                showMessage(appMessage, "Documento restaurado.", "success");
                await loadTrash();
            } catch (error) { showMessage(appMessage, error.message, "error"); }
        }, "primary"));
        documentsBody.append(row);
    });
    const trashedMessages = trash.mensajes_contacto || [];
    if (!trashedMessages.length) emptyRow(contactMessagesBody, 6, "No hay mensajes de contacto en la papelera.");
    trashedMessages.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.nombre);
        cell(row, item.correo);
        cell(row, item.asunto);
        cell(row, formatTrashDate(item.papelera_en));
        cell(row, trashExpiryDate(item.papelera_en));
        const actions = cell(row, "");
        actions.append(actionButton("Restaurar", async () => {
            try {
                await api(`/admin/mensajes-contacto/${item.id}/restaurar`, { method: "POST" });
                showMessage(appMessage, "Mensaje de contacto restaurado.", "success");
                await loadTrash();
            } catch (error) { showMessage(appMessage, error.message, "error"); }
        }, "primary"));
        contactMessagesBody.append(row);
    });
    if (adminUser?.es_admin_principal) {
        const trashedUsers = trash.usuarios || [];
        if (!trashedUsers.length) emptyRow(usersBody, 6, "No hay usuarios en la papelera.");
        trashedUsers.forEach((item) => {
            const row = document.createElement("tr");
            cell(row, item.nombre);
            cell(row, item.correo);
            const roles = { admin: "Administrador general", admin_contenido: "Administrador de contenido", directivo: "Directivo", profesor: "Profesor", alumno: "Alumno" };
            cell(row, roles[item.rol] || item.rol);
            cell(row, formatTrashDate(item.papelera_en));
            cell(row, trashExpiryDate(item.papelera_en));
            const actions = cell(row, "");
            actions.append(actionButton("Restaurar", async () => {
                try {
                    await api(`/admin/usuarios/${item.id}/restaurar`, { method: "POST" });
                    showMessage(appMessage, "Usuario restaurado; conserva su estado de acceso anterior.", "success");
                    await loadTrash();
                } catch (error) { showMessage(appMessage, error.message, "error"); }
            }, "primary"));
            usersBody.append(row);
        });
    }
}

function resetInformationForm() {
    const form = document.querySelector("#manual-information-form");
    form.reset();
    clearSelectedFiles("#manual-information-pdf");
    form.elements.id.value = "";
    form.elements.categoria.value = "Oferta educativa";
    form.elements.accion_avatar.value = "";
    form.elements.animacion.value = "Hablar";
    form.elements.emocion.value = "neutral";
    document.querySelector("#information-avatar-action-status").textContent = "";
    document.querySelector("#information-avatar-action-status").className = "";
    document.querySelector("#information-import-status").textContent = "";
    document.querySelector("#information-import-status").className = "message";
    document.querySelector("#information-drafts").replaceChildren();
    form.elements.activo.checked = true;
    document.querySelector("#manual-information-heading").textContent = "Agregar información";
    document.querySelector("#save-manual-information").textContent = "Guardar información";
    document.querySelector("#manual-information-pdf").disabled = false;
    document.querySelector("#cancel-information-edit").classList.add("hidden");
}

function editInformation(item) {
    const form = document.querySelector("#manual-information-form");
    form.elements.id.value = item.id;
    form.elements.clave.value = item.clave;
    form.elements.titulo.value = item.titulo;
    form.elements.contenido.value = item.contenido;
    form.elements.categoria.value = item.categoria;
    form.elements.accion_avatar.value = item.accion_avatar || "";
    form.elements.animacion.value = item.animacion || "Hablar";
    form.elements.emocion.value = item.emocion || "neutral";
    form.elements.activo.checked = item.activo;
    document.querySelector("#manual-information-heading").textContent = "Editar información";
    document.querySelector("#save-manual-information").textContent = "Guardar cambios";
    document.querySelector("#manual-information-pdf").disabled = false;
    document.querySelector("#cancel-information-edit").classList.remove("hidden");
    form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function setInformationActive(item, active) {
    try {
        await api(`/admin/informacion/${item.id}`, {
            method: "PUT",
            body: JSON.stringify({
                clave: item.clave,
                titulo: item.titulo,
                contenido: item.contenido,
                categoria: item.categoria,
                accion_avatar: item.accion_avatar || "",
                animacion: item.animacion || "Hablar",
                emocion: item.emocion || "neutral",
                activo,
            }),
        });
        showMessage(appMessage, active ? "Información reactivada para el kiosko." : "Información retirada del kiosko.", "success");
        await loadInformation();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

async function archiveInformation(item) {
    if (!window.confirm(`¿Eliminar “${item.titulo}” de la vista del kiosko? Se conservará archivada en el panel.`)) return;
    try {
        await api(`/admin/informacion/${item.id}`, { method: "DELETE" });
        showMessage(appMessage, "Información retirada del kiosko y conservada en administración.", "success");
        if (document.querySelector("#manual-information-form").elements.id.value === String(item.id)) resetInformationForm();
        await loadInformation();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

document.querySelector("#manual-information-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = document.querySelector("#save-manual-information");
    const status = document.querySelector("#manual-information-status");
    const files = Array.from(document.querySelector("#manual-information-pdf").files);
    const payload = {
        clave: form.elements.clave.value.trim(),
        titulo: form.elements.titulo.value.trim(),
        contenido: form.elements.contenido.value.trim(),
        categoria: form.elements.categoria.value.trim(),
        accion_avatar: form.elements.accion_avatar.value.trim(),
        animacion: form.elements.animacion.value,
        emocion: form.elements.emocion.value || "neutral",
        activo: form.elements.activo.checked,
    };
    if (files.length) {
        if (!document.querySelector("#information-public-confirmation").checked) {
            showMessage(status, "Confirma que la información es pública.", "error");
            return;
        }
        if (!validateAttachments(files, status)) return;
    }

    submit.disabled = true;
    showMessage(status, "Guardando información institucional...");
    try {
        if (files.length) await addAttachmentsToPayload(payload, files);
        const editingId = form.elements.id.value;
        let saved = null;
        if (editingId) {
            saved = await api(`/admin/informacion/${editingId}`, { method: "PUT", body: JSON.stringify(payload) });
        } else {
            saved = await api("/admin/informacion/con-documento", { method: "POST", body: JSON.stringify(payload) });
        }
        resetInformationForm();
        const uploadedDocuments = saved?.documentos?.filter((document) => files.some((file) => file.name === document.nombre_archivo) && document.activo) || [];
        const hasPendingPdf = uploadedDocuments.some((document) => document.mime_type === "application/pdf" && document.estado_indice === "pendiente");
        const hasIndexError = uploadedDocuments.some((document) => document.mime_type === "application/pdf" && document.estado_indice === "error");
        const message = editingId
            ? files.length
                ? `${files.length} archivo(s) agregado(s); los PDF se indexarán para búsquedas.`
                : "Cambios guardados."
            : files.length
                ? hasIndexError
                    ? `${files.length} archivo(s) guardado(s); hubo un problema al ampliar el índice de uno o más PDF.`
                    : hasPendingPdf
                        ? `${files.length} archivo(s) guardado(s). Los PDF ya pueden buscarse y Gemini está ampliando el índice.`
                        : `${files.length} archivo(s) guardado(s); ya están disponibles en el kiosko.`
                : "Información publicada para el kiosko.";
        showMessage(status, message, !editingId && files.length && hasIndexError ? "error" : "success");
        await loadInformation();
    } catch (error) {
        showMessage(status, error.message, "error");
    } finally {
        submit.disabled = false;
    }
});

document.querySelector("#cancel-information-edit").addEventListener("click", resetInformationForm);

document.querySelectorAll("[data-generate-avatar-action]").forEach((button) => button.addEventListener("click", async () => {
    const isQuestion = button.dataset.generateAvatarAction === "question";
    const form = document.querySelector(isQuestion ? "#question-form" : "#manual-information-form");
    const status = document.querySelector(isQuestion ? "#question-avatar-action-status" : "#information-avatar-action-status");
    const files = Array.from(document.querySelector(isQuestion ? "#question-attachment" : "#manual-information-pdf").files);
    const title = isQuestion ? form.elements.pregunta.value.trim() : form.elements.titulo.value.trim();
    const content = isQuestion ? form.elements.respuesta.value.trim() : form.elements.contenido.value.trim();
    if (title.length < 2 || !content) {
        status.className = "error";
        status.textContent = isQuestion
            ? "Escribe la pregunta y su respuesta antes de generar la animación."
            : "Escribe el título y la información antes de generar la animación.";
        return;
    }

    button.disabled = true;
    status.className = "";
    status.textContent = "Gemini está analizando la información…";
    try {
        const result = await api("/admin/avatar/accion/generar", {
            method: "POST",
            body: JSON.stringify({
                tipo: isQuestion ? "pregunta" : "informacion",
                titulo: title,
                categoria: form.elements.categoria.value.trim() || "General",
                contenido: content.slice(0, 12000),
                palabras_clave: isQuestion ? form.elements.palabras_clave.value.trim() : "",
                archivos: files.map((file) => file.name),
            }),
        });
        form.elements.accion_avatar.value = result.accion_avatar;
        form.elements.animacion.value = result.animacion;
        form.elements.emocion.value = result.emocion;
        status.className = "success";
        status.textContent = result.metodo === "local"
            ? `Gemini no respondió; se completó con la sugerencia local: ${result.animacion}. Revisa y guarda cuando quieras.`
            : `Descripción lista · animación: ${result.animacion}. Revisa el texto y guarda cuando quieras.`;
    } catch (error) {
        status.className = "error";
        status.textContent = error.message || "No se pudo generar la animación.";
    } finally {
        button.disabled = false;
    }
}));

function applyInformationDraft(draft) {
    const form = document.querySelector("#manual-information-form");
    form.elements.id.value = "";
    form.elements.clave.value = draft.clave || "informacion-institucional";
    form.elements.titulo.value = draft.titulo || "";
    form.elements.categoria.value = draft.categoria || "General";
    form.elements.contenido.value = draft.contenido || "";
    form.elements.animacion.value = draft.animacion || "Hablar";
    form.elements.accion_avatar.value = draft.accion_avatar || "";
    form.elements.emocion.value = draft.emocion || "neutral";
    form.elements.activo.checked = true;
    document.querySelector("#manual-information-heading").textContent = "Revisar borrador de información";
    document.querySelector("#save-manual-information").textContent = "Guardar información";
    document.querySelector("#manual-information-form").scrollIntoView({ behavior: "smooth", block: "start" });
    const animationStatus = document.querySelector("#information-avatar-action-status");
    animationStatus.className = "success";
    animationStatus.textContent = `Borrador completado · animación sugerida: ${draft.animacion || "Hablar"}. Revisa los campos antes de guardar.`;
}

function showInformationDrafts(drafts) {
    const list = document.querySelector("#information-drafts");
    list.replaceChildren();
    if (!drafts.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Gemini no encontró fichas institucionales claras en el documento.";
        list.append(empty);
        return;
    }
    applyInformationDraft(drafts[0]);
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = `${drafts.length} borrador(es) propuestos. El primero ya está en el formulario; revisa sus campos y pulsa «Guardar información» cuando esté listo.`;
    list.append(note);
    drafts.forEach((draft) => {
        const card = document.createElement("article");
        card.className = "draft-item";
        const heading = document.createElement("h3");
        heading.textContent = draft.titulo || "Información sugerida";
        const summary = document.createElement("p");
        summary.className = "muted";
        summary.textContent = `${draft.categoria || "General"} · Animación: ${draft.animacion || "Hablar"}`;
        const actions = document.createElement("div");
        actions.className = "form-actions";
        const useDraft = actionButton("Usar este borrador", () => applyInformationDraft(draft), "secondary");
        actions.append(useDraft);
        card.append(heading, summary, actions);
        list.append(card);
    });
}

async function encodeBase64(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
        binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
}

const MAX_ATTACHMENT_COUNT = 20;
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_ATTACHMENT_TOTAL_BYTES = 20 * 1024 * 1024;
const ALLOWED_ATTACHMENT_EXTENSIONS = new Set(["pdf", "png", "jpg", "jpeg", "webp"]);
const selectedFileCollections = new WeakMap();

function setPickerFiles(input, files) {
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    selectedFileCollections.set(input, files);
    renderSelectedFiles(input);
}

function renderSelectedFiles(input) {
    const list = document.querySelector(input.dataset.selectedList);
    if (!list) return;
    list.replaceChildren();
    const files = selectedFileCollections.get(input) || [];
    files.forEach((file, index) => {
        const item = document.createElement("span");
        item.className = "selected-file";
        const name = document.createElement("span");
        name.textContent = file.name;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Quitar";
        remove.setAttribute("aria-label", `Quitar ${file.name} de los archivos seleccionados`);
        remove.addEventListener("click", () => {
            const remaining = [...(selectedFileCollections.get(input) || [])];
            remaining.splice(index, 1);
            setPickerFiles(input, remaining);
        });
        item.append(name, remove);
        list.append(item);
    });
    if (files.length) {
        const summary = document.createElement("span");
        summary.className = "muted selected-file-count";
        summary.textContent = `${files.length} archivo(s) seleccionado(s)`;
        list.prepend(summary);
    }
}

function setupMultiFilePicker(inputSelector, listSelector) {
    const input = document.querySelector(inputSelector);
    input.dataset.selectedList = listSelector;
    input.addEventListener("change", () => {
        const existing = selectedFileCollections.get(input) || [];
        const added = Array.from(input.files);
        const filesByKey = new Map();
        [...existing, ...added].forEach((file) => {
            const key = `${file.name}|${file.size}|${file.lastModified}`;
            filesByKey.set(key, file);
        });
        setPickerFiles(input, [...filesByKey.values()]);
    });
}

function clearSelectedFiles(inputSelector) {
    const input = document.querySelector(inputSelector);
    if (input) setPickerFiles(input, []);
}

setupMultiFilePicker("#question-attachment", "#question-selected-files");
setupMultiFilePicker("#manual-information-pdf", "#manual-information-selected-files");

function validateAttachments(files, messageElement) {
    if (files.length > MAX_ATTACHMENT_COUNT) {
        showMessage(messageElement, `Puedes adjuntar hasta ${MAX_ATTACHMENT_COUNT} archivos por guardado.`, "error");
        return false;
    }
    let totalBytes = 0;
    for (const file of files) {
        const extension = file.name.split(".").pop().toLowerCase();
        if (!ALLOWED_ATTACHMENT_EXTENSIONS.has(extension)) {
            showMessage(messageElement, "Adjunta únicamente PDF, PNG, JPG o WEBP.", "error");
            return false;
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
            showMessage(messageElement, `${file.name} supera el límite de 10 MB por archivo.`, "error");
            return false;
        }
        totalBytes += file.size;
    }
    if (totalBytes > MAX_ATTACHMENT_TOTAL_BYTES) {
        showMessage(messageElement, "El tamaño conjunto de los archivos no puede superar 20 MB por guardado.", "error");
        return false;
    }
    return true;
}

async function addAttachmentsToPayload(payload, files) {
    if (!files.length) return;
    payload.archivos_nombres = files.map((file) => file.name);
    payload.archivos_base64 = await Promise.all(files.map(encodeBase64));
    payload.contenido_publico_confirmado = true;
}

async function analyzeInformationDocument() {
    const files = Array.from(document.querySelector("#manual-information-pdf").files);
    const file = files[0];
    const submit = document.querySelector("#generate-information-drafts");
    const status = document.querySelector("#information-import-status");
    const drafts = document.querySelector("#information-drafts");
    if (document.querySelector("#manual-information-form").elements.id.value) {
        showMessage(status, "Primero cancela la edición actual para analizar un documento como borrador nuevo.", "error");
        return;
    }
    if (!file) {
        showMessage(status, "Selecciona un PDF, TXT o MD para analizar.", "error");
        return;
    }
    if (files.length !== 1) {
        showMessage(status, "Para analizar con Gemini, selecciona un solo documento.", "error");
        return;
    }
    if (!document.querySelector("#information-public-confirmation").checked) {
        showMessage(status, "Confirma que la información es pública.", "error");
        return;
    }
    const extension = file.name.toLowerCase().split(".").pop();
    if (!["pdf", "txt", "md"].includes(extension)) {
        showMessage(status, "Gemini analiza PDF, TXT o MD. Las imágenes se pueden adjuntar a una ficha.", "error");
        return;
    }
    const maximumFileSize = extension === "pdf" ? 10 * 1024 * 1024 : 2 * 1024 * 1024;
    if (file.size > maximumFileSize) {
        showMessage(status, extension === "pdf" ? "El PDF supera el límite de 10 MB." : "El archivo de texto supera el límite de 2 MB.", "error");
        return;
    }

    submit.disabled = true;
    drafts.replaceChildren();
    const originalButtonLabel = submit.textContent;
    submit.textContent = "Procesando documento…";
    const startedAt = Date.now();
    showMessage(status, "Leyendo el documento…");
    const progressTimer = window.setInterval(() => {
        const seconds = Math.floor((Date.now() - startedAt) / 1000);
        status.textContent = `Analizando el documento… ${seconds} s.`;
    }, 1000);
    try {
        const payload = {
            nombre_archivo: file.name,
            contenido_publico_confirmado: true,
        };
        if (extension === "pdf") payload.archivo_base64 = await encodeBase64(file);
        else if (extension === "txt" || extension === "md") payload.texto = await file.text();
        else throw new Error("Formato no admitido. Usa PDF, TXT o Markdown.");

        const result = await api("/admin/informacion/analizar", { method: "POST", body: JSON.stringify(payload) });
        const analysisStatus = result.aviso_analisis ? ` ${result.aviso_analisis}` : "";
        const draftStatus = result.borradores.length
            ? `${result.borradores.length} borrador(es) listos. Revisa y guarda.`
            : "No se encontraron datos para completar. Revisa el archivo.";
        showMessage(status, `${draftStatus}${analysisStatus}`, result.borradores.length ? "success" : "error");
        showInformationDrafts(result.borradores);
        if (extension !== "pdf") clearSelectedFiles("#manual-information-pdf");
    } catch (error) {
        showMessage(status, error.message, "error");
    } finally {
        window.clearInterval(progressTimer);
        submit.disabled = false;
        submit.textContent = originalButtonLabel;
    }
}

document.querySelector("#generate-information-drafts").addEventListener("click", analyzeInformationDocument);

async function loadRequests() {
    const body = document.querySelector("#requests-body");
    const items = await api("/admin/solicitudes");
    updatePendingRequestBadge(items.length);
    body.replaceChildren();
    if (!items.length) return emptyRow(body, 4, "No hay solicitudes pendientes.");
    items.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.nombre);
        cell(row, item.correo);
        cell(row, item.creado_en ? new Date(item.creado_en).toLocaleDateString("es-MX") : "—");
        const actions = document.createElement("td");
        const group = document.createElement("div");
        group.className = "row-actions";
        if (adminUser?.es_admin_principal) {
            group.append(actionButton("Aprobar", () => decideRequest(item.id, "aprobar"), "primary"));
            group.append(actionButton("Rechazar", () => decideRequest(item.id, "rechazar")));
        } else {
            group.textContent = "Requiere autorización del administrador principal";
        }
        actions.append(group);
        row.append(actions);
        body.append(row);
    });
}

function updatePendingRequestBadge(count) {
    const pending = Number.isFinite(Number(count)) ? Math.max(0, Number(count)) : 0;
    const badge = document.querySelector("#requests-pending-badge");
    if (!badge) return;
    badge.textContent = pending > 99 ? "99+" : String(pending);
    badge.classList.toggle("hidden", pending === 0);
    badge.setAttribute("aria-label", `${pending} ${pending === 1 ? "solicitud pendiente" : "solicitudes pendientes"}`);
}

async function refreshPendingRequestBadge() {
    const items = await api("/admin/solicitudes");
    updatePendingRequestBadge(items.length);
}

async function loadContactMessages() {
    const items = await api("/admin/mensajes-contacto");
    updateContactUnreadBadge(items);
    const pending = items.filter((item) => !item.contestado);
    const replied = items.filter((item) => item.contestado);
    renderContactMessageRows(document.querySelector("#contact-messages-body"), pending, false);
    renderContactMessageRows(document.querySelector("#contact-replied-body"), replied, true);
}

function renderContactMessageRows(body, items, isHistory) {
    body.replaceChildren();
    if (!items.length) {
        emptyRow(body, 6, isHistory ? "Todavía no hay mensajes respondidos." : "No hay mensajes pendientes de respuesta.");
        return;
    }
    items.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.creado_en ? new Date(item.creado_en).toLocaleString("es-MX") : "—");
        cell(row, item.nombre);
        const emailCell = document.createElement("td");
        const emailLink = document.createElement("a");
        emailLink.href = `mailto:${encodeURIComponent(item.correo).replace(/%40/gi, "@")}?subject=${encodeURIComponent(`Re: ${item.asunto}`)}`;
        emailLink.textContent = item.correo;
        emailCell.append(emailLink);
        row.append(emailCell);
        const contentCell = document.createElement("td");
        contentCell.className = "contact-message-cell";
        const subject = document.createElement("strong");
        subject.textContent = item.asunto;
        const message = document.createElement("p");
        message.textContent = item.mensaje;
        contentCell.append(subject, message);
        row.append(contentCell);
        if (isHistory) {
            cell(row, item.contestado_en ? new Date(item.contestado_en).toLocaleString("es-MX") : "Respondido", "status active");
        } else {
            cell(row, item.leido ? "Leído" : "Nuevo", `status ${item.leido ? "active" : "pending"}`);
        }
        const actions = document.createElement("td");
        const actionGroup = document.createElement("div");
        actionGroup.className = "row-actions";
        if (!isHistory && (!item.leido || adminUser?.rol !== "admin_contenido")) {
            actionGroup.append(actionButton(item.leido ? "Marcar nuevo" : "Marcar leído", async () => {
                try {
                    await api(`/admin/mensajes-contacto/${item.id}/leido`, {
                        method: "PATCH",
                        body: JSON.stringify({ leido: !item.leido }),
                    });
                    await loadContactMessages();
                } catch (error) { showMessage(appMessage, error.message, "error"); }
            }));
        }
        const viewMessage = document.createElement("button");
        viewMessage.className = "button secondary";
        viewMessage.type = "button";
        viewMessage.textContent = "Ver mensaje";
        viewMessage.addEventListener("click", () => {
            document.querySelector("#contact-message-detail-title").textContent = item.asunto || "Mensaje de contacto";
            document.querySelector("#contact-message-detail-meta").textContent = [
                item.nombre,
                item.correo,
                item.creado_en ? new Date(item.creado_en).toLocaleString("es-MX") : "",
            ].filter(Boolean).join(" · ");
            document.querySelector("#contact-message-detail-body").textContent = item.mensaje || "(Sin contenido)";
            document.querySelector("#contact-message-dialog").showModal();
        });
        actionGroup.append(viewMessage);

        const reply = document.createElement("button");
        reply.className = "button primary";
        reply.type = "button";
        reply.textContent = isHistory ? "Responder de nuevo" : "Responder";
        reply.addEventListener("click", () => {
            const dialog = document.querySelector("#contact-reply-dialog");
            const form = document.querySelector("#contact-reply-form");
            form.dataset.messageId = String(item.id);
            document.querySelector("#contact-reply-recipient").textContent = `${item.nombre} · ${item.correo}`;
            document.querySelector("#contact-reply-subject").value = `Re: ${item.asunto}`;
            document.querySelector("#contact-reply-body").value = `Hola ${item.nombre},\n\n`;
            contactReplyAttachments = [];
            document.querySelector("#contact-reply-file-input").value = "";
            renderContactReplyAttachments();
            showMessage(document.querySelector("#contact-reply-status"), "");
            dialog.showModal();
            document.querySelector("#contact-reply-body").focus();
        });
        actionGroup.append(reply);
        actionGroup.append(actionButton("Mover a papelera", async () => {
            if (!window.confirm(`¿Mover el mensaje de ${item.nombre} a la papelera? Podrás restaurarlo durante 30 días.`)) return;
            try {
                await api(`/admin/mensajes-contacto/${item.id}/papelera`, { method: "POST" });
                showMessage(appMessage, "Mensaje movido a la papelera.", "success");
                await loadContactMessages();
            } catch (error) { showMessage(appMessage, error.message, "error"); }
        }));
        actions.append(actionGroup);
        row.append(actions);
        body.append(row);
    });
}

function formatFileSize(bytes) {
    return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function renderContactReplyAttachments() {
    const list = document.querySelector("#contact-reply-attachments");
    list.replaceChildren();
    contactReplyAttachments.forEach((attachment, index) => {
        const item = document.createElement("li");
        item.className = "contact-attachment-item";
        const name = document.createElement("span");
        name.textContent = `${attachment.nombre} · ${formatFileSize(attachment.size)}`;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "contact-attachment-remove";
        remove.textContent = "Quitar";
        remove.setAttribute("aria-label", `Quitar ${attachment.nombre}`);
        remove.addEventListener("click", () => {
            contactReplyAttachments.splice(index, 1);
            renderContactReplyAttachments();
        });
        item.append(name, remove);
        list.append(item);
    });
}

async function addContactReplyFiles(fileList) {
    const status = document.querySelector("#contact-reply-status");
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const allowedExtensions = new Set(["pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"]);
    const additions = [];
    let totalBytes = contactReplyAttachments.reduce((sum, attachment) => sum + attachment.size, 0);
    for (const file of files) {
        const extension = file.name.split(".").pop()?.toLowerCase();
        const image = ["png", "jpg", "jpeg", "gif", "webp"].includes(extension);
        if (!allowedExtensions.has(extension)) {
            showMessage(status, `No se admite el archivo “${file.name}”.`, "error");
            continue;
        }
        if (contactReplyAttachments.length + additions.length >= maxContactReplyAttachments) {
            showMessage(status, "Puedes adjuntar hasta 10 archivos por respuesta.", "error");
            break;
        }
        if (totalBytes + file.size > maxContactReplyBytes) {
            showMessage(status, "Los archivos no pueden superar 17 MB en total.", "error");
            continue;
        }
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(new Error("No se pudo leer el archivo."));
                reader.readAsDataURL(file);
            });
            additions.push({ nombre: file.name, size: file.size, contenido_base64: String(dataUrl).split(",", 2)[1] });
            totalBytes += file.size;
        } catch (error) {
            showMessage(status, error.message, "error");
        }
    }
    contactReplyAttachments.push(...additions);
    renderContactReplyAttachments();
    if (additions.length) showMessage(status, `${additions.length} archivo(s) adjuntado(s).`, "success");
}

function updateContactUnreadBadge(items) {
    const unread = items.filter((item) => !item.leido).length;
    const badge = document.querySelector("#contact-unread-badge");
    badge.textContent = unread > 99 ? "99+" : String(unread);
    badge.classList.toggle("hidden", unread === 0);
    badge.setAttribute("aria-label", `${unread} ${unread === 1 ? "mensaje sin leer" : "mensajes sin leer"}`);
}

function showContactNotification(message) {
    const notice = document.querySelector("#contact-notification");
    document.querySelector("#contact-notification-text").textContent = `Nuevo mensaje de contacto de ${message.nombre}.`;
    notice.classList.remove("hidden");
    window.clearTimeout(notice.dismissTimer);
    notice.dismissTimer = window.setTimeout(() => notice.classList.add("hidden"), 10000);
}

async function handleContactEvent(message) {
    if (knownContactMessageIds?.has(message.id)) return;
    knownContactMessageIds ??= new Set();
    knownContactMessageIds.add(message.id);
    const badge = document.querySelector("#contact-unread-badge");
    const currentCount = Number.parseInt(badge.textContent, 10) || 0;
    const updatedCount = currentCount + 1;
    badge.textContent = updatedCount > 99 ? "99+" : String(updatedCount);
    badge.classList.remove("hidden");
    badge.setAttribute("aria-label", `${updatedCount} mensajes sin leer`);
    showContactNotification(message);
    if (document.querySelector('[data-page="contact-messages"]:not(.hidden)')) {
        try { await loadContactMessages(); } catch { /* La notificación sigue disponible aunque falle la bandeja. */ }
    }
}

async function streamContactNotifications(signal) {
    while (!signal.aborted && ["admin", "admin_contenido"].includes(adminUser?.rol)) {
        try {
            const response = await fetch(`${API}/admin/mensajes-contacto/eventos`, {
                headers: { Authorization: `Bearer ${token()}` },
                cache: "no-store",
                signal,
            });
            if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let pending = "";
            while (!signal.aborted) {
                const { value, done } = await reader.read();
                if (done) break;
                pending += decoder.decode(value, { stream: true });
                let boundary;
                while ((boundary = pending.indexOf("\n\n")) >= 0) {
                    const block = pending.slice(0, boundary);
                    pending = pending.slice(boundary + 2);
                    const dataLine = block.split(/\r?\n/).find((line) => line.startsWith("data: "));
                    if (dataLine) {
                        try { await handleContactEvent(JSON.parse(dataLine.slice(6))); } catch { /* Ignora eventos malformados. */ }
                    }
                }
            }
        } catch {
            if (signal.aborted) return;
        }
        if (!signal.aborted && ["admin", "admin_contenido"].includes(adminUser?.rol)) {
            await new Promise((resolve) => window.setTimeout(resolve, 1500));
        }
    }
}

async function initializeContactNotifications() {
    try {
        const items = await api("/admin/mensajes-contacto");
        knownContactMessageIds = new Set(items.map((item) => item.id));
        updateContactUnreadBadge(items);
    } catch {
        knownContactMessageIds = new Set();
    }
    if (!["admin", "admin_contenido"].includes(adminUser?.rol)) return;
    contactStreamController?.abort();
    contactStreamController = new AbortController();
    void streamContactNotifications(contactStreamController.signal);
}

async function decideRequest(id, decision) {
    try {
        await api(`/admin/solicitudes/${id}`, { method: "PUT", body: JSON.stringify({ decision }) });
        showMessage(appMessage, `Solicitud ${decision === "aprobar" ? "aprobada" : "rechazada"}.`, "success");
        await loadRequests();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

async function loadUsers() {
    const body = document.querySelector("#users-body");
    const items = await api("/admin/usuarios?limite=200");
    body.replaceChildren();
    if (!items.length) return emptyRow(body, 5, "No hay usuarios registrados.");
    items.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.nombre);
        cell(row, item.correo);
        const roleCell = document.createElement("td");
        if (adminUser?.es_admin_principal) {
            if (item.rol === "admin") {
                roleCell.textContent = "Administrador general (protegido)";
                roleCell.title = "Esta cuenta no se puede eliminar, desactivar ni cambiar de rol.";
            } else {
                const roleSelect = document.createElement("select");
                roleSelect.setAttribute("aria-label", `Rol de ${item.nombre}`);
                [["admin_contenido", "Administrador de contenido"], ["directivo", "Directivo"], ["profesor", "Profesor"], ["alumno", "Alumno"]].forEach(([value, label]) => {
                    const option = document.createElement("option");
                    option.value = value;
                    option.textContent = label;
                    roleSelect.append(option);
                });
                roleSelect.value = item.rol;
                roleSelect.addEventListener("change", async () => {
                    const previous = item.rol;
                    try {
                        await api(`/admin/usuarios/${item.id}/rol`, { method: "PATCH", body: JSON.stringify({ rol: roleSelect.value }) });
                        showMessage(appMessage, `Rol de ${item.nombre} actualizado.`, "success");
                        await loadUsers();
                    } catch (error) {
                        roleSelect.value = previous;
                        showMessage(appMessage, error.message, "error");
                    }
                });
                roleCell.append(roleSelect);
            }
        } else {
            roleCell.textContent = item.rol;
        }
        row.append(roleCell);
        cell(row, item.estado_solicitud, `status ${item.estado_solicitud}`);
        const actions = document.createElement("td");
        if (adminUser?.es_admin_principal) {
            const group = document.createElement("div");
            group.className = "row-actions";
            if (item.rol === "admin") {
                if (!item.activo) group.append(actionButton("Reactivar cuenta protegida", () => setUserActive(item.id, true), "primary"));
                else {
                    const protectedStatus = actionButton("Cuenta protegida", () => {}, "secondary");
                    protectedStatus.disabled = true;
                    group.append(protectedStatus);
                }
            } else {
                group.append(actionButton(item.activo ? "Desactivar" : "Activar", () => setUserActive(item.id, !item.activo)));
            }
            if (item.rol !== "admin" && item.id !== adminUser.id && !item.es_admin_principal) {
                const remove = actionButton("Eliminar", () => trashUser(item), "secondary");
                remove.title = "Mueve esta cuenta a la papelera; podrás restaurarla durante 30 días.";
                group.append(remove);
            }
            actions.append(group);
        } else {
            actions.textContent = "Solo lectura";
        }
        row.append(actions);
        body.append(row);
    });
}

async function trashUser(item) {
    if (!window.confirm(`¿Mover la cuenta de ${item.nombre} a la papelera? Se bloqueará su acceso y se eliminará automáticamente después de 30 días.`)) return;
    try {
        await api(`/admin/usuarios/${item.id}/papelera`, { method: "POST" });
        showMessage(appMessage, "Usuario eliminado de la lista y enviado a la papelera. Su acceso quedó bloqueado.", "success");
        await loadUsers();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

async function setUserActive(id, activo) {
    try {
        await api(`/admin/usuarios/${id}/estado`, { method: "PATCH", body: JSON.stringify({ activo }) });
        showMessage(appMessage, `Usuario ${activo ? "activado" : "desactivado"}.`, "success");
        await loadUsers();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
}

async function loadMetrics() {
    const days = document.querySelector("#metric-days").value;
    const data = await api(`/admin/metricas?dias=${encodeURIComponent(days)}`);
    document.querySelector("#metrics-total").textContent = `${data.atenciones} consultas`;
    const chart = document.querySelector("#metrics-chart");
    chart.replaceChildren();
    const values = data.series || [];
    if (!values.length) {
        chart.textContent = "No hay consultas en este periodo.";
        return;
    }
    const maximum = Math.max(...values.map((item) => item.consultas), 1);
    values.forEach((item) => {
        const row = document.createElement("div");
        row.className = "chart-row";
        const date = document.createElement("span");
        date.textContent = new Date(`${item.fecha}T12:00:00`).toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
        const track = document.createElement("div");
        track.className = "chart-track";
        const bar = document.createElement("div");
        bar.className = "chart-bar";
        bar.style.width = `${Math.max(2, (item.consultas / maximum) * 100)}%`;
        track.append(bar);
        const count = document.createElement("span");
        count.className = "chart-count";
        count.textContent = item.consultas;
        row.append(date, track, count);
        chart.append(row);
    });
}

async function loadHealthStatus() {
    const status = document.querySelector("#service-health");
    try {
        const response = await fetch("/health", { cache: "no-store" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Servicio no disponible");
        status.textContent = `API: ${data.api} · MySQL: ${data.mysql}`;
        status.className = "service-health healthy";
    } catch (error) {
        status.textContent = `API o MySQL: ${error.message}`;
        status.className = "service-health unavailable";
    }
}

async function loadHistory() {
    const body = document.querySelector("#history-body");
    const params = new URLSearchParams({ limite: "500" });
    const from = document.querySelector("#history-from").value;
    const to = document.querySelector("#history-to").value;
    if (from) params.set("desde", from);
    if (to) params.set("hasta", to);
    const rows = await api(`/admin/historial?${params}`);
    body.replaceChildren();
    document.querySelector("#history-status").textContent = `${rows.length} consulta(s) mostrada(s), máximo 500.`;
    if (!rows.length) return emptyRow(body, 6, "No hay consultas en este periodo.");
    rows.forEach((item) => {
        const row = document.createElement("tr");
        cell(row, item.fecha_consulta ? new Date(item.fecha_consulta).toLocaleString("es-MX") : "—");
        cell(row, item.categoria || "Sin clasificar");
        const moduleLabels = {
            preguntas_respuestas: "Preguntas y respuestas",
            informacion_institucional: "Información institucional",
            aclaracion: "Aclaración",
            conversacion: "Saludo y conversación",
            sin_coincidencia: "Sin coincidencia",
            consulta_anterior: "Consulta anterior (sin módulo registrado)",
            consulta_general: "Consulta general",
        };
        cell(row, moduleLabels[item.modulo] || item.modulo || "Consulta anterior");
        cell(row, item.mensaje);
        cell(row, item.respuesta);
        cell(row, item.origen);
        body.append(row);
    });
}

async function showAdmin(user) {
    adminUser = user;
    accessScreen.classList.add("hidden");
    adminScreen.classList.remove("hidden");
    document.querySelector("#admin-name").textContent = user.nombre || user.correo || "Administrador";
    const isContentAdmin = user.rol === "admin_contenido";
    document.querySelector("#admin-role").textContent = user.es_admin_principal
        ? "Administrador principal"
        : isContentAdmin ? "Administrador de contenido" : "Administrador general";
    document.querySelectorAll("[data-view]").forEach((item) => {
        item.classList.toggle("hidden", isContentAdmin && !contentAdminViews.has(item.dataset.view));
    });
    document.querySelector("#users-open-trash")?.classList.toggle("hidden", !user.es_admin_principal);
    document.querySelector("#trash-users-section")?.classList.toggle("hidden", isContentAdmin || !user.es_admin_principal);
    document.querySelector("#contact-notification")?.classList.add("hidden");
    document.querySelector("#metric-attentions")?.closest(".metric")?.classList.toggle("hidden", false);
    document.querySelector("#metric-pending")?.closest(".metric")?.classList.toggle("hidden", isContentAdmin);
    document.querySelector("#requests-pending-badge")?.classList.toggle("hidden", isContentAdmin);
    document.querySelector("#popular-questions")?.closest(".content-section")?.classList.toggle("hidden", false);
    document.querySelector("#history-purge")?.classList.toggle("hidden", isContentAdmin);
    document.querySelector("#service-health-section")?.classList.toggle("hidden", isContentAdmin);
    if (healthPollTimer) window.clearInterval(healthPollTimer);
    if (requestPollTimer) window.clearInterval(requestPollTimer);
    contactStreamController?.abort();
    void initializeContactNotifications();
    if (!isContentAdmin) {
        loadHealthStatus();
        healthPollTimer = window.setInterval(loadHealthStatus, 30000);
        void refreshPendingRequestBadge().catch(() => {});
        requestPollTimer = window.setInterval(() => { void refreshPendingRequestBadge().catch(() => {}); }, 30000);
    }
    setView("summary");
}

async function restoreSession() {
    // Cada entrada al panel solicita iniciar sesión de nuevo.
    sessionStorage.removeItem(tokenKey);
    adminUser = null;
    if (healthPollTimer) window.clearInterval(healthPollTimer);
    if (requestPollTimer) window.clearInterval(requestPollTimer);
    contactStreamController?.abort();
    adminScreen.classList.add("hidden");
    accessScreen.classList.remove("hidden");
    setAccessTab("login");
}

document.querySelectorAll("[data-access-tab]").forEach((button) => button.addEventListener("click", () => setAccessTab(button.dataset.accessTab)));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelector("#contact-notification-open")?.addEventListener("click", () => {
    document.querySelector("#contact-notification")?.classList.add("hidden");
    setView("contact-messages");
});
document.querySelector("#users-open-trash")?.addEventListener("click", () => setView("trash"));
document.querySelector("#contact-messages-refresh")?.addEventListener("click", () => {
    loadContactMessages().catch((error) => showMessage(appMessage, error.message, "error"));
});
initContentDictation();

document.querySelector("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
        const response = await api("/auth/login", { method: "POST", body: JSON.stringify(data) });
        sessionStorage.setItem(tokenKey, response.access_token);
        await showAdmin(await api("/auth/me"));
    } catch (error) { showMessage(accessMessage, error.message, "error"); }
});

document.querySelector("#register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    if (data.contrasena !== data.confirmacion) return showMessage(accessMessage, "Las contraseñas no coinciden.", "error");
    delete data.confirmacion;
    try {
        const response = await api("/auth/register", { method: "POST", body: JSON.stringify(data) });
        form.reset();
        syncPrincipalRecoveryFields();
        setAccessTab("login");
        showMessage(accessMessage, response.mensaje || "Solicitud enviada para autorización.", "success");
    } catch (error) { showMessage(accessMessage, error.message, "error"); }
});

function syncPrincipalRecoveryFields() {
    const form = document.querySelector("#register-form");
    const isGeneralAdmin = form.elements.rol.value === "admin";
    if (!isGeneralAdmin) form.elements.clave_relevo.value = "";
    const recoveryProvided = Boolean(form.elements.clave_relevo.value.trim());
    document.querySelector("#principal-recovery-field").classList.toggle("hidden", !isGeneralAdmin);
    document.querySelector("#principal-recovery-help").classList.toggle("hidden", !isGeneralAdmin);
    form.elements.clave_autorizacion.required = !(isGeneralAdmin && recoveryProvided);
}

document.querySelector('#register-form select[name="rol"]').addEventListener("change", syncPrincipalRecoveryFields);
document.querySelector('#register-form input[name="clave_relevo"]').addEventListener("input", syncPrincipalRecoveryFields);
syncPrincipalRecoveryFields();

document.querySelector("#forgot-password-button").addEventListener("click", () => {
    const loginEmail = document.querySelector('#login-form input[name="correo"]').value.trim();
    const recoveryForm = document.querySelector("#forgot-password-form");
    recoveryForm.elements.correo.value = loginEmail;
    document.querySelector(".access-tabs").classList.add("hidden");
    document.querySelectorAll("[data-access-form]").forEach((form) => form.classList.add("hidden"));
    document.querySelector("#forgot-password-button").classList.add("hidden");
    recoveryForm.classList.remove("hidden");
    document.querySelector("#reset-password-form").classList.add("hidden");
    showMessage(accessMessage, "");
    recoveryForm.elements.correo.focus();
});

document.querySelector("#forgot-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) return form.reportValidity();
    const email = form.elements.correo.value.trim().toLowerCase();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
        const response = await api("/auth/forgot-password", { method: "POST", body: JSON.stringify({ correo: email }) });
        const resetForm = document.querySelector("#reset-password-form");
        resetForm.elements.correo.value = email;
        form.classList.add("hidden");
        resetForm.classList.remove("hidden");
        showMessage(accessMessage, response.mensaje || "Si el correo corresponde a una cuenta activa, enviaremos un código.", "success");
        resetForm.elements.codigo.focus();
    } catch (error) {
        showMessage(accessMessage, error.message, "error");
    } finally {
        submit.disabled = false;
    }
});

document.querySelector("#reset-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.checkValidity()) return form.reportValidity();
    if (form.elements.contrasena_nueva.value !== form.elements.confirmacion.value) {
        return showMessage(accessMessage, "Las contraseñas no coinciden.", "error");
    }
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
        const response = await api("/auth/reset-password", {
            method: "POST",
            body: JSON.stringify({
                correo: form.elements.correo.value.trim().toLowerCase(),
                codigo: form.elements.codigo.value.trim(),
                contrasena_nueva: form.elements.contrasena_nueva.value,
            }),
        });
        const email = form.elements.correo.value;
        form.reset();
        setAccessTab("login");
        document.querySelector('#login-form input[name="correo"]').value = email;
        showMessage(accessMessage, response.mensaje || "Contraseña actualizada. Ya puedes iniciar sesión.", "success");
    } catch (error) {
        showMessage(accessMessage, error.message, "error");
    } finally {
        submit.disabled = false;
    }
});

document.querySelectorAll("[data-recovery-back]").forEach((button) => button.addEventListener("click", () => {
    const email = document.querySelector("#reset-password-form").elements.correo.value
        || document.querySelector("#forgot-password-form").elements.correo.value;
    document.querySelector("#forgot-password-form").reset();
    document.querySelector("#reset-password-form").reset();
    setAccessTab("login");
    if (email) document.querySelector('#login-form input[name="correo"]').value = email;
}));

document.querySelector("#question-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const files = Array.from(document.querySelector("#question-attachment").files);
    const id = values.id;
    delete values.id;
    delete values.archivo;
    values.activo = form.elements.activo.checked;
    values.palabras_clave ||= null;
    if (files.length) {
        if (!document.querySelector("#question-public-confirmation").checked) {
            showMessage(appMessage, "Confirma que la información es pública.", "error");
            return;
        }
        if (!validateAttachments(files, appMessage)) return;
        await addAttachmentsToPayload(values, files);
    }
    try {
        const saved = await api(id ? `/admin/preguntas/${id}` : "/admin/preguntas", { method: id ? "PUT" : "POST", body: JSON.stringify(values) });
        form.reset();
        clearSelectedFiles("#question-attachment");
        form.elements.activo.checked = true;
        document.querySelector("#question-avatar-action-status").textContent = "";
        document.querySelector("#question-avatar-action-status").className = "";
        document.querySelector("#question-autocomplete-status").textContent = "No se guarda hasta pulsar «Guardar respuesta».";
        document.querySelector("#question-autocomplete-status").className = "muted";
        const pendingPdf = saved?.documentos?.some((doc) => files.some((file) => file.name === doc.nombre_archivo) && doc.activo && doc.estado_indice === "pendiente");
        showMessage(appMessage, files.length
            ? pendingPdf ? `Respuesta guardada con ${files.length} archivo(s). Los PDF se están indexando para búsquedas.` : `Respuesta guardada con ${files.length} archivo(s).`
            : "Respuesta guardada.", "success");
        await loadQuestions();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
});

document.querySelector("#question-reset").addEventListener("click", () => {
    const form = document.querySelector("#question-form");
    form.reset();
    clearSelectedFiles("#question-attachment");
    form.elements.id.value = "";
    form.elements.activo.checked = true;
    document.querySelector("#question-avatar-action-status").textContent = "";
    document.querySelector("#question-avatar-action-status").className = "";
    document.querySelector("#question-autocomplete-status").textContent = "No se guarda hasta pulsar «Guardar respuesta».";
});

document.querySelector("#question-autocomplete").addEventListener("click", async () => {
    const input = document.querySelector("#question-attachment");
    const files = Array.from(input.files);
    const status = document.querySelector("#question-autocomplete-status");
    const button = document.querySelector("#question-autocomplete");
    if (files.length !== 1) {
        status.textContent = "Selecciona un solo PDF, TXT o MD.";
        status.className = "error";
        return;
    }
    if (!document.querySelector("#question-public-confirmation").checked) {
        status.textContent = "Confirma que la información es pública.";
        status.className = "error";
        return;
    }
    const file = files[0];
    const extension = file.name.toLowerCase().split(".").pop();
    if (!["pdf", "txt", "md"].includes(extension)) {
        status.textContent = "Para autocompletar, usa PDF, TXT o MD.";
        status.className = "error";
        return;
    }
    const maximumSize = extension === "pdf" ? 10 * 1024 * 1024 : 2 * 1024 * 1024;
    if (file.size > maximumSize) {
        status.textContent = extension === "pdf" ? "El PDF supera 10 MB." : "El archivo de texto supera 2 MB.";
        status.className = "error";
        return;
    }

    button.disabled = true;
    const label = button.textContent;
    button.textContent = "Procesando documento…";
    status.className = "muted";
    status.textContent = "Analizando el documento…";
    try {
        const payload = { nombre_archivo: file.name, contenido_publico_confirmado: true };
        if (extension === "pdf") payload.archivo_base64 = await encodeBase64(file);
        else payload.texto = await file.text();
        const result = await api("/admin/informacion/analizar", { method: "POST", body: JSON.stringify(payload) });
        const draft = result.borradores?.[0];
        if (!draft) throw new Error(result.aviso_analisis || "No se encontraron datos para completar. Revisa el archivo.");
        const form = document.querySelector("#question-form");
        const title = (draft.titulo || "Información institucional").trim().replace(/[?.!]+$/, "");
        form.elements.categoria.value = draft.categoria || "General";
        form.elements.pregunta.value = /^[¿].*\?$/.test(draft.titulo || "")
            ? draft.titulo
            : `¿Qué información contiene el apartado «${title}»?`;
        form.elements.respuesta.value = draft.contenido || "";
        form.elements.palabras_clave.value = [draft.categoria, draft.titulo].filter(Boolean).join(", ").slice(0, 255);
        form.elements.animacion.value = draft.animacion || "Hablar";
        form.elements.accion_avatar.value = draft.accion_avatar || "";
        form.elements.emocion.value = draft.emocion || "neutral";
        status.className = "success";
        status.textContent = "Pregunta, respuesta y animación listas. Revisa y guarda.";
        if (extension !== "pdf") clearSelectedFiles("#question-attachment");
    } catch (error) {
        status.className = "error";
        status.textContent = error.message || "No se pudo completar la pregunta y respuesta.";
    } finally {
        button.disabled = false;
        button.textContent = label;
    }
});
document.querySelector("#questions-search").addEventListener("input", () => {
    window.clearTimeout(questionsSearchTimer);
    questionsSearchTimer = window.setTimeout(() => {
        questionsPage = 1;
        loadQuestions().catch((error) => showMessage(appMessage, error.message, "error"));
    }, 250);
});
document.querySelector("#questions-category").addEventListener("change", () => {
    questionsPage = 1;
    loadQuestions().catch((error) => showMessage(appMessage, error.message, "error"));
});
document.querySelector("#questions-prev").addEventListener("click", () => {
    if (questionsPage > 1) { questionsPage -= 1; loadQuestions().catch((error) => showMessage(appMessage, error.message, "error")); }
});
document.querySelector("#questions-next").addEventListener("click", () => {
    questionsPage += 1;
    loadQuestions().catch((error) => showMessage(appMessage, error.message, "error"));
});
document.querySelector("#history-search").addEventListener("click", () => loadHistory().catch((error) => showMessage(appMessage, error.message, "error")));
document.querySelector("#history-purge").addEventListener("click", async () => {
    const from = document.querySelector("#history-from").value;
    const to = document.querySelector("#history-to").value;
    if (!from || !to) return showMessage(appMessage, "Elige las dos fechas para depurar el historial.", "error");
    if (from > to) return showMessage(appMessage, "La fecha inicial no puede ser posterior a la fecha final.", "error");
    if (!window.confirm(`¿Eliminar definitivamente las consultas del ${from} al ${to}? Esta acción no se puede deshacer.`)) return;
    try {
        const result = await api(`/admin/historial?desde=${encodeURIComponent(from)}&hasta=${encodeURIComponent(to)}`, { method: "DELETE" });
        showMessage(appMessage, `Se eliminaron ${result.eliminados} consulta(s).`, "success");
        await loadHistory();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
});
document.querySelector("#metric-days").addEventListener("change", () => loadMetrics().catch((error) => showMessage(appMessage, error.message, "error")));
document.querySelector("#download-backup").addEventListener("click", async (event) => {
    if (!window.confirm("El respaldo puede contener datos personales y hashes de contraseñas. ¿Deseas descargarlo en este dispositivo?")) return;
    const button = event.currentTarget;
    const message = document.querySelector("#backup-message");
    button.disabled = true;
    showMessage(message, "Preparando el respaldo…");
    try {
        const response = await fetch(`${API}/admin/respaldo`, { headers: { Authorization: `Bearer ${token()}` } });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || `Error ${response.status}`);
        }
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "lobo_upvt_db.sql";
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
        showMessage(message, "Respaldo descargado. Guárdalo en un lugar privado.", "success");
    } catch (error) {
        showMessage(message, error.message, "error");
    } finally {
        button.disabled = false;
    }
});
document.querySelector("#logout-button").addEventListener("click", () => {
    if (healthPollTimer) window.clearInterval(healthPollTimer);
    if (requestPollTimer) window.clearInterval(requestPollTimer);
    contactStreamController?.abort();
    sessionStorage.removeItem(tokenKey);
    adminUser = null;
    adminScreen.classList.add("hidden");
    accessScreen.classList.remove("hidden");
    document.querySelector("#login-form").reset();
    setAccessTab("login");
});

const profileDialog = document.querySelector("#profile-dialog");
const profileForm = document.querySelector("#profile-form");
document.querySelector("#profile-button").addEventListener("click", async () => {
    try {
        adminUser = await api("/auth/me");
        profileForm.elements.nombre.value = adminUser.nombre || "";
        profileForm.elements.contrasena_actual.value = "";
        profileForm.elements.contrasena_nueva.value = "";
        showMessage(document.querySelector("#profile-message"), "");
        profileDialog.showModal();
    } catch (error) { showMessage(appMessage, error.message, "error"); }
});
document.querySelector("#profile-close").addEventListener("click", () => profileDialog.close());
document.querySelector("#contact-message-close").addEventListener("click", () => {
    document.querySelector("#contact-message-dialog").close();
});
document.querySelector("#contact-reply-close").addEventListener("click", () => {
    document.querySelector("#contact-reply-dialog").close();
});
const contactReplyFileInput = document.querySelector("#contact-reply-file-input");
document.querySelector("#contact-attach-files").addEventListener("click", () => contactReplyFileInput.click());
contactReplyFileInput.addEventListener("change", async () => {
    await addContactReplyFiles(contactReplyFileInput.files);
    contactReplyFileInput.value = "";
});
document.querySelector("#contact-reply-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const sendButton = document.querySelector("#contact-reply-send");
    const statusMessage = document.querySelector("#contact-reply-status");
    sendButton.disabled = true;
    showMessage(statusMessage, "Enviando respuesta…");
    try {
        await api(`/admin/mensajes-contacto/${encodeURIComponent(form.dataset.messageId)}/responder`, {
            method: "POST",
            body: JSON.stringify({
                mensaje: document.querySelector("#contact-reply-body").value,
                adjuntos: contactReplyAttachments.map(({ nombre, contenido_base64 }) => ({ nombre, contenido_base64 })),
            }),
        });
        document.querySelector("#contact-reply-dialog").close();
        showMessage(appMessage, contactReplyAttachments.length
            ? `Respuesta y ${contactReplyAttachments.length} archivo(s) enviado(s) al correo del visitante.`
            : "Respuesta enviada al correo del visitante.", "success");
        contactReplyAttachments = [];
        await loadContactMessages();
    } catch (error) {
        showMessage(statusMessage, error.message, "error");
    } finally {
        sendButton.disabled = false;
    }
});
document.querySelector("#profile-forgot-password").addEventListener("click", () => {
    const email = adminUser?.correo || "";
    profileDialog.close();
    if (healthPollTimer) window.clearInterval(healthPollTimer);
    if (requestPollTimer) window.clearInterval(requestPollTimer);
    contactStreamController?.abort();
    sessionStorage.removeItem(tokenKey);
    adminUser = null;
    adminScreen.classList.add("hidden");
    accessScreen.classList.remove("hidden");
    setAccessTab("login");
    document.querySelector('#login-form input[name="correo"]').value = email;
    document.querySelector("#forgot-password-button").click();
});
document.querySelector("#download-summary-report").addEventListener("click", downloadDashboardReport);
profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const current = profileForm.elements.contrasena_actual.value;
    const next = profileForm.elements.contrasena_nueva.value;
    if (Boolean(current) !== Boolean(next)) {
        showMessage(document.querySelector("#profile-message"), "Para cambiar la contraseña completa ambos campos.", "error");
        return;
    }
    const payload = { nombre: profileForm.elements.nombre.value.trim() };
    if (current && next) {
        payload.contrasena_actual = current;
        payload.contrasena_nueva = next;
    }
    try {
        adminUser = await api("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });
        document.querySelector("#admin-name").textContent = adminUser.nombre;
        profileForm.elements.contrasena_actual.value = "";
        profileForm.elements.contrasena_nueva.value = "";
        showMessage(document.querySelector("#profile-message"), "Perfil actualizado.", "success");
    } catch (error) { showMessage(document.querySelector("#profile-message"), error.message, "error"); }
});

restoreSession();
