'use strict';

window.addEventListener('DOMContentLoaded', () => {
    const search = document.getElementById('cameo-search');
    const received = document.getElementById('received-only');
    const status = document.getElementById('refresh-status');
    let timer;
    let refreshing = false;

    function filter() {
        const query = search.value.trim().toLocaleLowerCase();
        document.querySelectorAll('.cameo-card').forEach(card => {
            card.hidden = !card.dataset.search.includes(query) || (received.checked && card.dataset.received !== 'true');
        });
        document.querySelectorAll('.category, .faction').forEach(section => {
            section.hidden = !section.querySelector('.cameo-card:not([hidden])');
        });
    }
    search.addEventListener('input', filter);
    received.addEventListener('change', filter);

    function schedule() {
        clearTimeout(timer);
        if (document.getElementById('omega-tracker').dataset.offline === 'true') {
            status.textContent = 'Offline design preview · sample inventory';
            return;
        }
        const second = Number(document.getElementById('omega-tracker').dataset.second);
        const delay = ((second + 3 - new Date().getSeconds() + 60) % 60) || 60;
        timer = setTimeout(refresh, delay * 1000);
    }

    async function refresh() {
        if (document.getElementById('omega-tracker').dataset.offline === 'true') return;
        if (refreshing) return;
        if (document.hidden) { schedule(); return; }
        refreshing = true;
        try {
            const response = await fetch(window.location.href, {cache: 'no-cache', credentials: 'same-origin'});
            if (response.status !== 304) {
                if (!response.ok) throw new Error('Tracker unavailable');
                const page = new DOMParser().parseFromString(await response.text(), 'text/html');
                const next = page.getElementById('omega-tracker');
                if (!next) throw new Error('Invalid tracker response');
                const previous = document.getElementById('omega-tracker');
                const openKeys = new Set(Array.from(previous.querySelectorAll('details[open][data-key]'), element => element.dataset.key));
                const focused = document.activeElement.closest('details[data-key]')?.dataset.key;
                const scroll = window.scrollY;
                previous.replaceWith(next);
                next.querySelectorAll('details[data-key]').forEach(element => {
                    element.open = openKeys.has(element.dataset.key);
                    if (focused === element.dataset.key) element.querySelector('summary').focus({preventScroll: true});
                });
                filter();
                window.scrollTo(0, scroll);
            }
            status.textContent = `Updated ${new Date().toLocaleTimeString()}`;
        } catch (error) {
            status.textContent = 'Update failed; retrying next minute';
        } finally {
            refreshing = false;
            schedule();
        }
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    filter();
    schedule();
});
