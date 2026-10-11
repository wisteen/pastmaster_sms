const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/js/quiz-attempt.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
const response = data => ({ ok: true, headers: { get: () => 'application/json' }, json: async () => data });

function harness({ saved = null, transport, remaining = 60000 } = {}) {
    const events = new Map(), timers = new Map(), intervals = [];
    let tick = 0, nextTimer = 0;
    const node = extra => Object.assign({ value: '', textContent: '', disabled: false, hidden: false, style: {},
        addEventListener(type, fn) { events.set(`${this.id}:${type}`, fn); }, setAttribute() {} }, extra);
    const fields = [node({ id: 'answer', name: 'question_1', value: 'A', tagName: 'INPUT', checked: true }), node({ id: 'theory', name: 'theory_2', value: 'Explanation', tagName: 'TEXTAREA' })];
    const nodes = Object.fromEntries(['submit-btn', 'save-status', 'quiz-warning', 'progress', 'timer'].map(id => [id, node({ id })]));
    const form = node({ id: 'quiz-form', action: '/submit', querySelector: () => ({ value: 'csrf' }), querySelectorAll: () => fields });
    nodes['quiz-form'] = form;
    const config = { deadline: new Date(remaining).toISOString(), serverNow: new Date(0).toISOString(), saveUrl: '/save', integrityUrl: '/integrity', resultUrl: '/result', storageKey: 'draft', tabSwitches: 0, maxTabSwitches: 3 };
    nodes['quiz-config'] = { textContent: JSON.stringify(config) };
    const storage = new Map(saved ? [['draft', JSON.stringify(saved)]] : []);
    const requests = [], redirects = [];
    class FormData {
        constructor(source) {
            this.data = new Map();
            if (source) fields.filter(field => !field.disabled && (field.tagName === 'TEXTAREA' || field.checked)).forEach(field => this.data.set(field.name, field.value));
        }
        set(key, value) { this.data.set(key, value); }
        get(key) { return this.data.get(key); }
    }
    const context = vm.createContext({ console, Date, JSON, Promise, AbortController, FormData,
        performance: { now: () => tick },
        navigator: { onLine: true }, confirm: () => true,
        setTimeout: (fn, delay) => { const id = ++nextTimer; timers.set(id, { fn, delay }); return id; },
        clearTimeout: id => timers.delete(id), setInterval: (fn, delay) => intervals.push({ fn, delay }),
        localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
        location: { href: '/attempt', assign: url => redirects.push(url) },
        window: { addEventListener: (type, fn) => events.set(`window:${type}`, fn) },
        document: {
            getElementById: id => nodes[id] || null, querySelector: () => node({}),
            querySelectorAll: () => fields.map((field, index) => ({ dataset: { number: index + 1 }, querySelector: () => field.checked ? field : null, querySelectorAll: () => field.tagName === 'TEXTAREA' ? [field] : [] })),
            addEventListener: (type, fn) => events.set(`document:${type}`, fn),
        },
        fetch: async (url, options) => { requests.push({ url, data: options.body }); return transport ? transport(url, options) : response(url === '/submit' ? { submitted: true, result_url: '/result' } : { saved: true }); },
    });
    vm.runInContext(script, context);
    return { fields, nodes, storage, requests, redirects,
        async submit() { events.get('quiz-form:submit')({ preventDefault() {} }); await flush(); },
        async edit(value) { fields[1].value = value; events.get('theory:input')(); for (const { fn, delay } of [...timers.values()]) if (delay === 600) fn(); await flush(); },
        async advance(ms) { tick += ms; intervals.find(item => item.delay === 1000).fn(); await flush(); },
        async online() { events.get('window:online')(); await flush(); },
    };
}

test('recovers local answers and clears the draft only after server confirmation', async () => {
    const h = harness({ saved: { question_1: [], theory_2: 'Recovered text' } });
    await flush();
    assert.equal(h.fields[0].checked, false);
    assert.equal(h.fields[1].value, 'Recovered text');
    assert.equal(h.requests[0].data.get('theory_2'), 'Recovered text');
    assert.equal(h.storage.has('draft'), false);
});

test('failed autosave keeps edited answers locally and retries on reconnect', async () => {
    let offline = true;
    const h = harness({ transport: async () => { if (offline) throw Error('offline'); return response({ saved: true }); } });
    await flush();
    await h.edit('Do not lose this');
    assert.equal(JSON.parse(h.storage.get('draft')).theory_2, 'Do not lose this');
    assert.match(h.nodes['save-status'].textContent, /Not saved online/);
    offline = false;
    await h.online();
    assert.equal(h.requests.at(-1).data.get('theory_2'), 'Do not lose this');
    assert.equal(h.storage.has('draft'), false);
});

test('failed final submission re-enables fields and retry sends all answers', async () => {
    let fail = true;
    const h = harness({ transport: async url => {
        if (url === '/submit' && fail) throw Error('offline');
        return response(url === '/submit' ? { submitted: true, result_url: '/result' } : { saved: true });
    } });
    await flush();
    await h.submit();
    assert.equal(h.fields[0].disabled, false);
    assert.equal(h.nodes['submit-btn'].textContent, 'Retry submission');
    assert.equal(h.storage.has('draft'), true);
    fail = false;
    await h.submit();
    assert.equal(h.requests.at(-1).data.get('question_1'), 'A');
    assert.equal(h.requests.at(-1).data.get('theory_2'), 'Explanation');
    assert.deepEqual(h.redirects, ['/result']);
    assert.equal(h.storage.has('draft'), false);
});

test('deadline uses server time and automatic submission retains selected answers', async () => {
    const h = harness({ remaining: 2000 });
    await flush();
    assert.equal(h.nodes.timer.textContent, '0:02');
    await h.advance(2100);
    assert.equal(h.requests.at(-1).url, '/submit');
    assert.equal(h.requests.at(-1).data.get('question_1'), 'A');
    assert.deepEqual(h.redirects, ['/result']);
});

test('final submission waits for in-flight save and blocks duplicate submit clicks', async () => {
    const pending = deferred();
    const h = harness({ transport: async url => url === '/save' ? pending.promise : response({ submitted: true, result_url: '/result' }) });
    await flush();
    await h.submit();
    await h.submit();
    assert.equal(h.requests.length, 1);
    assert.equal(h.fields[0].disabled, true);
    pending.resolve(response({ saved: true }));
    await flush();
    assert.deepEqual(h.requests.map(item => item.url), ['/save', '/submit']);
    assert.equal(h.requests[1].data.get('question_1'), 'A');
    assert.deepEqual(h.redirects, ['/result']);
});
