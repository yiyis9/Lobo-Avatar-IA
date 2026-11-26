import 'bootstrap';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/600.css';
import '@fontsource/dm-sans/700.css';
import '../css/app.css';

const toggle = document.querySelector('[data-sidebar-toggle]');
const sidebar = document.querySelector('[data-sidebar]');
const scrim = document.querySelector('[data-sidebar-scrim]');

function setSidebar(open) {
    sidebar?.classList.toggle('mobile-open', open);
    scrim?.classList.toggle('visible', open);
    toggle?.setAttribute('aria-expanded', String(open));
}

toggle?.addEventListener('click', () => setSidebar(!sidebar?.classList.contains('mobile-open')));
scrim?.addEventListener('click', () => setSidebar(false));
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setSidebar(false);
});

document.querySelectorAll('[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
        const message = form.getAttribute('data-confirm');
        if (message && !window.confirm(message)) event.preventDefault();
    });
});
