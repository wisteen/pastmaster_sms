const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../templates/teacher/component_results.html'), 'utf8');
const script = template.match(/<script>([\s\S]*?)<\/script>/)[1];
const components = [{ id: 1, component_name: 'CE', weight: 30, max_score: 30 }, { id: 2, component_name: 'Exam', weight: 70, max_score: 70 }];
const student = { id: 1, name: 'Learner', student_id: 'S001', component_scores: { 1: 0, 2: null }, total_score: 0, grade: 'F' };
function response(data, ok = true) { return { ok, redirected: false, json: async () => data }; }
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
function harness() {
    const nodes = new Map();
    const node = id => {
        if (!nodes.has(id)) nodes.set(id, { value: '', textContent: '', innerHTML: '', className: '', disabled: false,
            dataset: {}, style: {}, addEventListener() {}, classList: { add() {}, remove() {}, toggle() {} } });
        return nodes.get(id);
    };
    node('class_select').value = '1'; node('subject_select').value = '2'; node('term_select').value = '3';
    const context = vm.createContext({ URLSearchParams, console,
        document: { getElementById: node, addEventListener() {}, cookie: 'csrftoken=test', querySelector: () => null },
        window: { addEventListener() {} },
        fetch: async url => response(url.includes('get-components') ? { components } : { students: [structuredClone(student)], results_locked: false })
    });
    vm.runInContext(script, context);
    const input = (value, componentId = '1') => ({ value, max: '70', dataset: { studentId: '1', componentId, termId: '3', savedValue: '5' }, style: {}, disabled: false });
    return { context, node, input };
}

test('saved zero marks and totals stay visible; missing marks stay blank', async () => {
    const { context, node } = harness();
    await context.loadResults();
    assert.match(node('results_body').innerHTML, /data-saved-value="0" value="0"/);
    assert.match(node('results_body').innerHTML, /data-saved-value="" value=""/);
    assert.match(node('results_body').innerHTML, /id="total_1">0<\/span>/);
});

test('blank, negative, excessive and over-precise marks are not sent as zero', async () => {
    const { context, input } = harness();
    await context.loadResults();
    let calls = 0;
    context.fetch = () => { calls++; throw Error('Unexpected save'); };
    for (const value of ['', '-1', '99', '5.123']) {
        const field = input(value);
        await context.updateComponentScore(field);
        assert.equal(field.value, '5');
    }
    assert.equal(calls, 0);
});

test('save sends captured term and displays server grade, including custom grades', async () => {
    const { context, node, input } = harness();
    await context.loadResults();
    let payload;
    context.fetch = async (_, options) => {
        payload = JSON.parse(options.body);
        return response({ success: true, total_score: 12.5, grade: 'EX' });
    };
    await context.updateComponentScore(input('0'));
    assert.equal(payload.score, '0');
    assert.equal(payload.term_id, '3');
    assert.equal(node('total_1').textContent, 12.5);
    assert.equal(node('grade_1').textContent, 'EX');
    assert.match(node('grade_chart').innerHTML, /EX/);
});

test('late responses cannot overwrite a more recent term selection', async () => {
    const { context, node } = harness();
    const pending = Array.from({ length: 4 }, deferred);
    let calls = 0;
    context.fetch = () => pending[calls++].promise;
    const oldLoad = context.loadResults();
    node('term_select').value = '4';
    const newLoad = context.loadResults();
    pending[2].resolve(response({ components }));
    pending[3].resolve(response({ students: [{ ...student, name: 'NewTermLearner' }] }));
    await newLoad;
    pending[0].resolve(response({ components }));
    pending[1].resolve(response({ students: [{ ...student, name: 'OldTermLearner' }] }));
    await oldLoad;
    assert.match(node('results_body').innerHTML, /NewTermLearner/);
    assert.doesNotMatch(node('results_body').innerHTML, /OldTermLearner/);
    assert.equal(vm.runInContext('loadedSelection.term_id', context), '4');
});

test('failed save restores the saved value and reports the failure', async () => {
    const { context, node, input } = harness();
    await context.loadResults();
    context.fetch = async () => response({ success: false, message: 'Results are published' });
    const field = input('20');
    await context.updateComponentScore(field);
    assert.equal(field.value, '5');
    assert.match(node('results_status').textContent, /not saved.*published/);
    assert.equal(field.disabled, false);
});

test('student saves are serialized and selection stays fixed until they finish', async () => {
    const { context, node, input } = harness();
    await context.loadResults();
    const pending = [deferred(), deferred()];
    let calls = 0;
    context.fetch = () => pending[calls++].promise;
    const first = context.updateComponentScore(input('10'));
    const second = context.updateComponentScore(input('20', '2'));
    await Promise.resolve();
    assert.equal(calls, 1);
    assert.equal(node('term_select').disabled, true);
    node('term_select').value = '9';
    await context.loadResults();
    assert.equal(node('term_select').value, '3');
    pending[0].resolve(response({ success: true, total_score: 10, grade: 'D' }));
    await first;
    pending[1].resolve(response({ success: true, total_score: 30, grade: 'C' }));
    await second;
    assert.equal(calls, 2);
    assert.equal(node('total_1').textContent, 30);
    assert.equal(node('term_select').disabled, false);
});

test('API errors are visible and do not leave editable stale results', async () => {
    const { context, node } = harness();
    await context.loadResults();
    context.fetch = async () => response({ error: 'Result access disabled' }, false);
    await context.loadResults();
    assert.match(node('results_status').textContent, /Result access disabled/);
    assert.equal(vm.runInContext('loadedSelection', context), null);
});

test('published results are disabled and cannot submit edits', async () => {
    const { context, node, input } = harness();
    context.fetch = async url => response(url.includes('get-components') ? { components } : { students: [student], results_locked: true, lock_message: 'Published term' });
    await context.loadResults();
    assert.match(node('results_body').innerHTML, / disabled onchange=/);
    let calls = 0;
    context.fetch = () => { calls++; };
    await context.updateComponentScore(input('20'));
    assert.equal(calls, 0);
});

test('student names are escaped rather than inserted as HTML', async () => {
    const { context, node } = harness();
    context.fetch = async url => response(url.includes('get-components') ? { components } : { students: [{ ...student, name: '<img src=x onerror=alert(1)>' }] });
    await context.loadResults();
    assert.doesNotMatch(node('results_body').innerHTML, /<img src=x/);
    assert.match(node('results_body').innerHTML, /&lt;img/);
});


