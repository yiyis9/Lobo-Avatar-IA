(() => {
    const storageKey = "lobo_accessibility_preferences";
    const defaults = { fontScale: 1, highContrast: false, underlineLinks: false, motion: "auto", textSpacing: false, simpleFont: false, hoverSpeech: true };
    let preferences = { ...defaults };
    try {
        preferences = { ...defaults, ...JSON.parse(localStorage.getItem(storageKey) || sessionStorage.getItem(storageKey) || "{}") };
    } catch { /* Keep accessible defaults when storage is unavailable. */ }
    preferences.fontScale = Math.min(2, Math.max(1, Number(preferences.fontScale) || 1));
    preferences.highContrast = preferences.highContrast === true;
    preferences.underlineLinks = preferences.underlineLinks === true;
    preferences.textSpacing = preferences.textSpacing === true;
    preferences.simpleFont = preferences.simpleFont === true;
    preferences.hoverSpeech = preferences.hoverSpeech !== false;
    if (!["auto", "reduced", "full"].includes(preferences.motion)) preferences.motion = "auto";

    const root = document.documentElement;
    const fontSizes = new Map();
    const skip = document.createElement("a");
    skip.className = "a11y-skip-link";
    skip.href = "#main-content";
    skip.textContent = "Saltar al contenido";
    skip.addEventListener("click", (event) => {
        event.preventDefault();
        const target = document.querySelector("#admin-screen:not(.hidden) .main-content")
            || document.querySelector("#access-screen:not(.hidden)")
            || document.querySelector("main.kiosk-main, main.entry-page");
        if (!target) return;
        target.setAttribute("tabindex", "-1");
        target.focus();
    });

    const toggle = document.createElement("button");
    toggle.className = "a11y-toggle";
    toggle.type = "button";
    toggle.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="4" r="1.8"/><path d="M4 8h16M12 8v5m0-5-4 4m4-4 4 4m-4 1-3 7m3-7 3 7"/></svg>';
    toggle.setAttribute("aria-label", "Abrir opciones de accesibilidad");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "a11y-panel");
    toggle.dataset.tooltip = "Abrir opciones de accesibilidad";

    const panel = document.createElement("section");
    panel.className = "a11y-panel";
    panel.id = "a11y-panel";
    panel.hidden = true;
    panel.setAttribute("aria-labelledby", "a11y-title");
    panel.innerHTML = `
        <h2 id="a11y-title">Accesibilidad</h2>
        <p id="a11y-text-status" aria-live="polite"></p>
        <div class="a11y-size-controls">
            <button type="button" data-a11y-action="smaller" aria-label="Reducir tamaño del texto" data-tooltip="Reduce el texto hasta su tamaño normal.">A−</button>
            <button type="button" data-a11y-action="larger" aria-label="Aumentar tamaño del texto" data-tooltip="Aumenta el texto hasta 200 por ciento.">A+</button>
        </div>
        <button type="button" data-a11y-action="spacing" aria-pressed="false" data-tooltip="Aumenta el espacio entre líneas, palabras y letras para facilitar la lectura.">Espaciado de lectura: desactivado</button>
        <button type="button" data-a11y-action="font" aria-pressed="false" data-tooltip="Usa una fuente de sistema sencilla, sin adornos.">Fuente sencilla: desactivada</button>
        <button type="button" data-a11y-action="contrast" aria-pressed="false" data-tooltip="Aumenta el contraste de texto, controles y fondos.">Alto contraste: desactivado</button>
        <button type="button" data-a11y-action="links" aria-pressed="false" data-tooltip="Hace más fácil distinguir los enlaces del texto.">Subrayar enlaces: desactivado</button>
        <button type="button" data-a11y-action="motion" aria-pressed="false" data-tooltip="Reduce animaciones y transiciones de la interfaz.">Reducir movimiento: desactivado</button>
        <button type="button" data-a11y-action="hover-speech" aria-pressed="true" data-tooltip="Lee en voz alta la etiqueta de los botones al pasar el cursor o llegar a ellos con el teclado.">Leer botones al pasar el cursor: activado</button>
        <button class="a11y-reset" type="button" data-a11y-action="reset" data-tooltip="Vuelve a las opciones de accesibilidad iniciales.">Restablecer opciones</button>
        <button class="a11y-close" type="button" data-a11y-close>Cerrar opciones</button>
    `;
    document.body.insertBefore(panel, document.body.firstChild);
    document.body.insertBefore(toggle, panel);
    document.body.insertBefore(skip, toggle);

    let tooltipId = 0;
    const tooltips = new WeakMap();
    let activeTooltipTrigger = null;
    function placeTooltip(element) {
        const tooltip = tooltips.get(element);
        if (!tooltip) return;
        const anchor = element.getBoundingClientRect();
        const margin = 10;
        const gap = 8;
        tooltip.style.maxHeight = `${Math.max(60, window.innerHeight - margin * 2)}px`;
        const size = tooltip.getBoundingClientRect();
        const above = anchor.top - margin - gap;
        const below = window.innerHeight - anchor.bottom - margin - gap;
        const placeAbove = above >= size.height || above >= below;
        const desiredTop = placeAbove ? anchor.top - size.height - gap : anchor.bottom + gap;
        const top = Math.min(Math.max(margin, desiredTop), window.innerHeight - margin - size.height);
        const desiredLeft = anchor.left + anchor.width / 2 - size.width / 2;
        const left = Math.min(Math.max(margin, desiredLeft), window.innerWidth - margin - size.width);
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        tooltip.classList.toggle("a11y-tooltip-below", !placeAbove);
    }
    function showTooltip(element) {
        const tooltip = tooltips.get(element);
        if (!tooltip) return;
        if (activeTooltipTrigger && activeTooltipTrigger !== element) {
            tooltips.get(activeTooltipTrigger)?.classList.remove("a11y-tooltip-visible");
        }
        activeTooltipTrigger = element;
        tooltip.classList.add("a11y-tooltip-visible");
        placeTooltip(element);
    }
    function hideTooltip(element) {
        if (!element || activeTooltipTrigger !== element) return;
        if (element.matches(":hover") || element.contains(document.activeElement)) return;
        tooltips.get(element)?.classList.remove("a11y-tooltip-visible", "a11y-tooltip-below");
        activeTooltipTrigger = null;
    }
    function enhanceTooltips(container) {
        const elements = [];
        if (container instanceof Element && container.matches("[title], [data-tooltip]")) elements.push(container);
        if (container.querySelectorAll) elements.push(...container.querySelectorAll("[title], [data-tooltip]"));
        elements.forEach((element) => {
            if (element.classList.contains("a11y-tooltip")) return;
            if (element.tagName === "IFRAME" && !element.dataset.tooltip) return;
            const text = element.dataset.tooltip || element.getAttribute("title");
            if (!text) return;
            if (element.matches("button, [role='button']")) {
                const currentLabel = (element.getAttribute("aria-label")
                    || [...element.childNodes]
                        .filter((child) => !(child instanceof Element && child.classList.contains("a11y-tooltip")))
                        .map((child) => child.textContent || "").join(" ")).trim();
                if (!currentLabel) element.setAttribute("aria-label", text);
            }
            let tooltip = [...element.children].find((child) => child.classList.contains("a11y-tooltip"));
            tooltip ||= tooltips.get(element);
            if (!tooltip) {
                tooltip = document.createElement("span");
                tooltip.className = "a11y-tooltip";
                tooltip.id = `a11y-tooltip-${++tooltipId}`;
                tooltip.setAttribute("role", "tooltip");
                document.body.append(tooltip);
                tooltips.set(element, tooltip);
                element.classList.add("a11y-tooltip-trigger");
                const descriptions = new Set((element.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
                descriptions.add(tooltip.id);
                element.setAttribute("aria-describedby", [...descriptions].join(" "));
            }
            tooltip.textContent = text;
            if (element.hasAttribute("title")) element.removeAttribute("title");
        });
    }
    function tooltipTrigger(target) {
        return target instanceof Element ? target.closest(".a11y-tooltip-trigger") : null;
    }
    document.addEventListener("pointerover", (event) => {
        const trigger = tooltipTrigger(event.target);
        const related = tooltipTrigger(event.relatedTarget);
        if (trigger && trigger !== related) showTooltip(trigger);
    });
    document.addEventListener("pointerout", (event) => {
        const trigger = tooltipTrigger(event.target);
        const related = tooltipTrigger(event.relatedTarget);
        if (trigger && trigger !== related) hideTooltip(trigger);
    });
    document.addEventListener("focusin", (event) => showTooltip(tooltipTrigger(event.target)));
    document.addEventListener("focusout", (event) => {
        const trigger = tooltipTrigger(event.target);
        if (trigger) window.setTimeout(() => hideTooltip(trigger), 0);
    });
    window.addEventListener("resize", () => {
        if (activeTooltipTrigger) placeTooltip(activeTooltipTrigger);
    });
    window.addEventListener("scroll", () => {
        if (activeTooltipTrigger) placeTooltip(activeTooltipTrigger);
    }, true);

    function save() {
        try { localStorage.setItem(storageKey, JSON.stringify(preferences)); } catch { /* Storage is optional. */ }
    }

    function setFontScale() {
        fontSizes.forEach((record, element) => {
            if (record.inlineValue) element.style.setProperty("font-size", record.inlineValue, record.priority);
            else element.style.removeProperty("font-size");
        });
        fontSizes.clear();
        if (preferences.fontScale <= 1) {
            document.querySelector("#a11y-text-status").textContent = "Tamaño del texto: 100%.";
            return;
        }
        const candidates = [...document.body.querySelectorAll("*")].filter((element) => {
            if (element.closest(".a11y-toggle, .a11y-skip-link, .a11y-panel")) return false;
            if (/^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName)) return true;
            return [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
        }).map((element) => ({
            element,
            record: {
                size: Number.parseFloat(getComputedStyle(element).fontSize) || 16,
                inlineValue: element.style.getPropertyValue("font-size"),
                priority: element.style.getPropertyPriority("font-size"),
            },
        }));
        candidates.forEach(({ element, record }) => {
            fontSizes.set(element, record);
            element.style.setProperty("font-size", `${record.size * preferences.fontScale}px`, "important");
        });
        document.querySelector("#a11y-text-status").textContent = `Tamaño del texto: ${Math.round(preferences.fontScale * 100)}%.`;
    }

    function applyPreferences() {
        root.dataset.a11yContrast = preferences.highContrast ? "high" : "normal";
        root.dataset.a11yLinks = preferences.underlineLinks ? "underlined" : "normal";
        root.dataset.a11ySpacing = preferences.textSpacing ? "wide" : "normal";
        root.dataset.a11yFont = preferences.simpleFont ? "simple" : "normal";
        if (preferences.motion === "auto") delete root.dataset.a11yMotion;
        else root.dataset.a11yMotion = preferences.motion;
        panel.querySelector('[data-a11y-action="contrast"]').setAttribute("aria-pressed", String(preferences.highContrast));
        panel.querySelector('[data-a11y-action="contrast"]').textContent = `Alto contraste: ${preferences.highContrast ? "activado" : "desactivado"}`;
        panel.querySelector('[data-a11y-action="links"]').setAttribute("aria-pressed", String(preferences.underlineLinks));
        panel.querySelector('[data-a11y-action="links"]').textContent = `Subrayar enlaces: ${preferences.underlineLinks ? "activado" : "desactivado"}`;
        panel.querySelector('[data-a11y-action="spacing"]').setAttribute("aria-pressed", String(preferences.textSpacing));
        panel.querySelector('[data-a11y-action="spacing"]').textContent = `Espaciado de lectura: ${preferences.textSpacing ? "activado" : "desactivado"}`;
        panel.querySelector('[data-a11y-action="font"]').setAttribute("aria-pressed", String(preferences.simpleFont));
        panel.querySelector('[data-a11y-action="font"]').textContent = `Fuente sencilla: ${preferences.simpleFont ? "activada" : "desactivada"}`;
        panel.querySelector('[data-a11y-action="hover-speech"]').setAttribute("aria-pressed", String(preferences.hoverSpeech));
        panel.querySelector('[data-a11y-action="hover-speech"]').textContent = `Leer botones al pasar el cursor: ${preferences.hoverSpeech ? "activado" : "desactivado"}`;
        const reducedMotion = preferences.motion === "reduced" || (preferences.motion === "auto" && matchMedia("(prefers-reduced-motion: reduce)").matches);
        panel.querySelector('[data-a11y-action="motion"]').setAttribute("aria-pressed", String(reducedMotion));
        panel.querySelector('[data-a11y-action="motion"]').textContent = `Reducir movimiento: ${reducedMotion ? "activado" : "desactivado"}`;
        panel.querySelector('[data-a11y-action="smaller"]').disabled = preferences.fontScale <= 1;
        panel.querySelector('[data-a11y-action="larger"]').disabled = preferences.fontScale >= 2;
        setFontScale();
    }

    function updateToggleLabel(open) {
        const label = `${open ? "Cerrar" : "Abrir"} opciones de accesibilidad`;
        toggle.setAttribute("aria-label", label);
        toggle.dataset.tooltip = label;
        const tooltip = [...toggle.children].find((child) => child.classList.contains("a11y-tooltip"));
        if (tooltip) tooltip.textContent = label;
    }

    toggle.addEventListener("click", () => {
        const open = panel.hidden;
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        updateToggleLabel(open);
        if (open) panel.querySelector("button:not(:disabled)")?.focus();
    });
    panel.querySelector("[data-a11y-close]").addEventListener("click", () => {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        updateToggleLabel(false);
        toggle.focus();
    });
    document.addEventListener("pointerdown", (event) => {
        if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) {
            panel.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
            updateToggleLabel(false);
        }
    });
    panel.querySelectorAll("[data-a11y-action]").forEach((button) => button.addEventListener("click", () => {
        switch (button.dataset.a11yAction) {
            case "smaller": preferences.fontScale = Math.max(1, Math.round((preferences.fontScale - 0.1) * 10) / 10); break;
            case "larger": preferences.fontScale = Math.min(2, Math.round((preferences.fontScale + 0.1) * 10) / 10); break;
            case "spacing": preferences.textSpacing = !preferences.textSpacing; break;
            case "font": preferences.simpleFont = !preferences.simpleFont; break;
            case "hover-speech": preferences.hoverSpeech = !preferences.hoverSpeech; if (!preferences.hoverSpeech) cancelHoverSpeech(); break;
            case "contrast": preferences.highContrast = !preferences.highContrast; break;
            case "links": preferences.underlineLinks = !preferences.underlineLinks; break;
            case "motion": preferences.motion = preferences.motion === "reduced" ? "full" : "reduced"; break;
            case "reset": preferences = { ...defaults }; break;
        }
        applyPreferences();
        save();
        panel.querySelector("#a11y-text-status").textContent = `Opciones actualizadas. Texto al ${Math.round(preferences.fontScale * 100)} por ciento; alto contraste ${preferences.highContrast ? "activado" : "desactivado"}; espaciado ${preferences.textSpacing ? "activado" : "desactivado"}; lectura de botones ${preferences.hoverSpeech ? "activada" : "desactivada"}.`;
    }));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            panel.hidden = true;
            toggle.setAttribute("aria-expanded", "false");
            updateToggleLabel(false);
            toggle.focus();
        }
    });
    let speechTimer = 0;
    let lastSpokenButton = null;
    let activeHoverUtterance = null;
    let pendingHoverButton = null;
    function cancelHoverSpeech() {
        window.clearTimeout(speechTimer);
        speechTimer = 0;
        pendingHoverButton = null;
        if (activeHoverUtterance && window.speechSynthesis) {
            const kioskSpeaking = document.querySelector("#form-status")?.textContent.includes("Lobo está hablando");
            if (!kioskSpeaking) window.speechSynthesis.cancel();
            activeHoverUtterance = null;
        }
    }
    function speakButtonLabel(button) {
        if (!preferences.hoverSpeech || !window.speechSynthesis || !window.SpeechSynthesisUtterance) return;
        if (!(button instanceof HTMLElement) || button.matches(":disabled, [aria-disabled='true']") || button.closest("[aria-hidden='true']")) return;
        const kioskStatus = document.querySelector("#form-status");
        if (kioskStatus?.textContent.includes("Lobo está hablando")) {
            pendingHoverButton = button;
            return;
        }
        const visibleLabel = [...button.childNodes]
            .filter((child) => !(child instanceof Element && child.classList.contains("a11y-tooltip")))
            .map((child) => child.textContent || "").join(" ").replace(/\s+/g, " ").trim();
        const label = (button.getAttribute("aria-label") || visibleLabel || button.dataset.tooltip || button.title || "")
            .replace(/\s+/g, " ").trim();
        if (!label || label.length > 120 || label === lastSpokenButton) return;
        window.clearTimeout(speechTimer);
        cancelHoverSpeech();
        speechTimer = window.setTimeout(() => {
            speechTimer = 0;
            if (!preferences.hoverSpeech) return;
            if (kioskStatus?.textContent.includes("Lobo está hablando")) {
                pendingHoverButton = button;
                return;
            }
            const utterance = new SpeechSynthesisUtterance(label);
            utterance.lang = "es-MX";
            utterance.rate = 1.06;
            utterance.pitch = 1;
            const spanishVoices = window.speechSynthesis.getVoices().filter((voice) => /^es(-|_)/i.test(voice.lang));
            const mexicanVoice = spanishVoices.find((voice) => /^es[-_]MX/i.test(voice.lang));
            const preferredVoice = mexicanVoice || spanishVoices[0];
            if (preferredVoice) utterance.voice = preferredVoice;
            utterance.onend = utterance.onerror = () => {
                if (activeHoverUtterance === utterance) activeHoverUtterance = null;
            };
            activeHoverUtterance = utterance;
            lastSpokenButton = label;
            window.speechSynthesis.speak(utterance);
        }, 90);
    }
    document.addEventListener("pointerover", (event) => {
        if (event.pointerType !== "mouse") return;
        const button = event.target instanceof Element ? event.target.closest("button, [role='button']") : null;
        const relatedButton = event.relatedTarget instanceof Element ? event.relatedTarget.closest("button, [role='button']") : null;
        if (button && button !== relatedButton) speakButtonLabel(button);
    });
    document.addEventListener("pointerout", (event) => {
        const button = event.target instanceof Element ? event.target.closest("button, [role='button']") : null;
        const relatedButton = event.relatedTarget instanceof Element ? event.relatedTarget.closest("button, [role='button']") : null;
        if (button && button !== relatedButton) {
            window.clearTimeout(speechTimer);
            if (pendingHoverButton === button) pendingHoverButton = null;
            lastSpokenButton = null;
        }
    });
    document.addEventListener("focusin", (event) => {
        const button = event.target instanceof Element ? event.target.closest("button, [role='button']") : null;
        if (button) speakButtonLabel(button);
    });
    document.addEventListener("focusout", (event) => {
        const button = event.target instanceof Element ? event.target.closest("button, [role='button']") : null;
        if (button && pendingHoverButton === button && !button.matches(":hover")) pendingHoverButton = null;
    });
    const kioskStatus = document.querySelector("#form-status");
    if (kioskStatus) {
        new MutationObserver(() => {
            if (kioskStatus.textContent.includes("Lobo está hablando") || !pendingHoverButton) return;
            const button = pendingHoverButton;
            pendingHoverButton = null;
            if (button.isConnected && (button.matches(":hover") || button === document.activeElement)) {
                speakButtonLabel(button);
            }
        }).observe(kioskStatus, { childList: true, subtree: true, characterData: true });
    }
    new MutationObserver((records) => {
        let addedElements = false;
        records.forEach((record) => {
            if (record.type === "attributes") enhanceTooltips(record.target);
            record.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    addedElements = true;
                    enhanceTooltips(node);
                }
            });
        });
        if (addedElements) setFontScale();
    }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["title"] });
    window.addEventListener("resize", () => {
        if (preferences.fontScale > 1) setFontScale();
    });
    enhanceTooltips(document.body);
    applyPreferences();
})();
