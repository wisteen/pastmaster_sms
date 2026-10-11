(() => {
    'use strict';
    const config = JSON.parse(document.getElementById('quiz-config').textContent);
    const form = document.getElementById('quiz-form');
    const button = document.getElementById('submit-btn');
    const status = document.getElementById('save-status');
    const warning = document.getElementById('quiz-warning');
    const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
    const remainingAtLoad = Date.parse(config.deadline) - Date.parse(config.serverNow);
    const loadedAt = performance.now();
    let submitted = false, submitting = false, revision = 0, debounce, awayAt = null;
    let queue = Promise.resolve(), expired = false, automaticRetry = false;
    const fields = [...form.querySelectorAll('input[name^=question_], textarea[name^=theory_]')];
    const warn = text => { warning.textContent = text; warning.hidden = false; };
    function snapshot() {
        const values = {};
        fields.forEach(field => {
            if (field.tagName === 'TEXTAREA') values[field.name] = field.value;
            else { values[field.name] ||= []; if (field.checked) values[field.name].push(field.value); }
        });
        return values;
    }
    function keepLocal() {
        try { localStorage.setItem(config.storageKey, JSON.stringify(snapshot())); } catch (_) {}
    }
    function progress() {
        let answered = 0;
        const cards = [...document.querySelectorAll('.quiz-question')];
        cards.forEach(card => {
            const complete = !!card.querySelector('input:checked') || [...card.querySelectorAll('textarea')].some(field => field.value.trim());
            answered += Number(complete);
            const jump = document.querySelector(`[data-jump="${card.dataset.number}"]`);
            jump.style.backgroundColor = complete ? '#d1fae5' : '';
            jump.setAttribute('aria-label', `Question ${card.dataset.number}, ${complete ? 'answered' : 'unanswered'}`);
        });
        document.getElementById('progress').textContent = `${answered} of ${cards.length} answered`;
        return cards.length - answered;
    }
    function completed(url) {
        submitted = true;
        try { localStorage.removeItem(config.storageKey); } catch (_) {}
        location.assign(url || config.resultUrl);
    }
    async function send(url, data) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 12000);
        try {
            const response = await fetch(url, {method:'POST', body:data, headers:{'X-CSRFToken':csrf, 'X-Requested-With':'XMLHttpRequest'}, signal:controller.signal});
            if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw Error('Request was not confirmed.');
            return await response.json();
        } finally { clearTimeout(timeout); }
    }
    function save() {
        if (submitted || submitting || expired) return queue;
        const data = new FormData(form), savedRevision = revision;
        queue = queue.catch(() => {}).then(async () => {
            if (submitted || submitting) return;
            status.textContent = 'Saving answers…';
            try {
                const result = await send(config.saveUrl, data);
                if (result.submitted) return completed(result.result_url);
                status.textContent = `Saved at ${new Date().toLocaleTimeString()}`;
                if (savedRevision === revision) { try { localStorage.removeItem(config.storageKey); } catch (_) {} }
            } catch (_) { status.textContent = 'Not saved online. Reconnect to retry; keep this page open.'; }
        });
        return queue;
    }
    async function submit(automatic = false) {
        if (submitted || submitting) return;
        if (!automatic) {
            const unanswered = progress();
            if (!confirm(unanswered ? `${unanswered} question(s) unanswered. Submit anyway?` : 'Submit your quiz? Answers cannot be changed afterwards.')) return;
        }
        keepLocal();
        submitting = true;
        clearTimeout(debounce);
        button.disabled = true;
        button.textContent = 'Submitting…';
        const finalData = new FormData(form);
        fields.forEach(field => { field.disabled = true; });
        try {
            await queue;
            if (submitted) return;
            const result = await send(form.action || location.href, finalData);
            if (!result.submitted) throw Error('Submission not confirmed.');
            completed(result.result_url);
        } catch (_) {
            submitting = false;
            fields.forEach(field => { field.disabled = false; });
            automaticRetry = automatic;
            button.disabled = false;
            button.textContent = 'Retry submission';
            warn('Submission is not confirmed. Reconnect and retry. After the deadline allowance, only answers already saved online can be submitted.');
        }
    }
    try {
        const saved = JSON.parse(localStorage.getItem(config.storageKey) || 'null');
        if (saved) {
            fields.forEach(field => {
                if (!(field.name in saved)) return;
                if (field.tagName === 'TEXTAREA') field.value = saved[field.name];
                else field.checked = saved[field.name].includes(field.value);
            });
            status.textContent = 'Recovered unsaved answers from this device. Reconnecting…';
        }
    } catch (_) {}
    fields.forEach(field => field.addEventListener('input', () => {
        revision++;
        keepLocal();
        progress();
        clearTimeout(debounce);
        debounce = setTimeout(save, 600);
    }));
    form.addEventListener('submit', event => { event.preventDefault(); submit(expired || automaticRetry); });
    window.addEventListener('online', () => { if (expired || automaticRetry) submit(true); else save(); });
    window.addEventListener('beforeunload', event => {
        if (!submitted) { keepLocal(); event.preventDefault(); event.returnValue = ''; }
    });
    async function integrity(eventType) {
        if (submitted || submitting) return;
        await save();
        const data = new FormData(); data.set('event_type', eventType);
        try {
            const result = await send(config.integrityUrl, data);
            config.tabSwitches = result.tab_switches;
            if (result.submitted) return completed(result.result_url);
            if (eventType === 'tab_switch') warn(`Tab switches: ${result.tab_switches}/${config.maxTabSwitches}. Stay on this quiz tab to avoid automatic submission.`);
        } catch (_) { status.textContent = 'Connection interrupted. Reconnect to save your progress.'; }
    }
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { awayAt = performance.now(); keepLocal(); save(); }
        else {
            if (config.detectTabs && awayAt !== null && performance.now() - awayAt >= 2000) integrity('tab_switch');
            awayAt = null;
        }
    });
    const fullscreen = document.getElementById('fullscreen-button');
    fullscreen?.addEventListener('click', async () => {
        try { await document.documentElement.requestFullscreen(); }
        catch (_) { warn('Full screen is unavailable on this device. You can continue the quiz here.'); }
    });
    let hadFullscreen = false;
    document.addEventListener('fullscreenchange', () => {
        if (document.fullscreenElement) hadFullscreen = true;
        else if (hadFullscreen && config.fullscreen) { warn('Full screen exited. Use Enter full screen to return.'); integrity('fullscreen_exit'); }
    });
    function tick() {
        const seconds = Math.max(0, Math.ceil((remainingAtLoad - (performance.now() - loadedAt)) / 1000));
        document.getElementById('timer').textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
        if (!seconds && !expired) { expired = true; fields.forEach(field => { if (field.tagName === 'TEXTAREA') field.readOnly = true; else field.addEventListener('click', event => event.preventDefault()); }); submit(true); }
    }
    progress(); tick(); save();
    setInterval(tick, 1000);
    setInterval(() => { if (automaticRetry && navigator.onLine) submit(true); else save(); }, 15000);
})();
