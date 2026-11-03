// Component behavior tests with deterministic hooks/timers and mocked HTTP.
// These exercise the actual TSX and API modules; they do not replace browser checks.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');

function load(relative, imports = {}, globals = {}) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', '__API_BASE_URL__');
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const context = { exports: {}, console: { error() {} },
    __API_BASE_URL__: '', AbortController, setTimeout, clearTimeout, ...globals,
    require(name) {
      if (name.endsWith('.css')) return {};
      assert.ok(name in imports, `Unexpected import: ${name}`);
      return imports[name];
    },
  };
  vm.runInNewContext(compiled, context);
  return context.exports;
}

function billingRecord(status = 'OCR_COMPLETE', id = 'rec-1') {
  const field = value => ({ normalizedValue: value, rawValue: value,
    confidence: null, quality: value == null ? 'MISSING' : 'OK' });
  return { recordId: id, status, fields: Object.fromEntries([
    ['bolNumber', 'BOL-1'], ['contractLifting', null], ['origin', 'Syracuse'],
    ['supplier', 'Supplier'], ['carrier', 'Carrier'], ['transactionDate', '2026-09-17'],
    ['destination', 'Albany'],
  ].map(([name, value]) => [name, field(value)])), lineItems: [
    { lineItemId: 'line-1', product: field('Gas'), grossGallons: field(100),
      netGallons: field(99), e3StockId: field(null) },
  ] };
}
function nodes(node, result = []) {
  if (!node || typeof node !== 'object') return result;
  if (Array.isArray(node)) { node.forEach(n => nodes(n, result)); return result; }
  result.push(node); nodes(node.props?.children, result); return result;
}
function content(node) {
  if (node == null || typeof node === 'boolean') return '';
  if (Array.isArray(node)) return node.map(content).join('');
  if (typeof node !== 'object') return String(node);
  return content(node.props?.children);
}
function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}
function mount(page, api) {
  const slots = [], timers = new Map();
  let cursor = 0, effects = [], dirty = false, tree, timer = 0, id = 'rec-1';
  const react = {
    useRef(value) {
      const i = cursor++;
      if (!slots[i]) slots[i] = { current: value };
      return slots[i];
    },
    useState(initial) {
      const i = cursor++;
      if (!slots[i]) slots[i] = { value: initial };
      return [slots[i].value, value => {
        const next = typeof value === 'function' ? value(slots[i].value) : value;
        if (next !== slots[i].value) { slots[i].value = next; dirty = true; }
      }];
    },
    useMemo(fn) { return fn(); },
    useEffect(fn, deps) {
      const i = cursor++, previous = slots[i];
      if (!previous || deps.some((d, n) => d !== previous.deps[n])) {
        effects.push(() => { previous?.cleanup?.(); slots[i] = { deps, cleanup: fn() }; });
      }
    },
  };
  const jsx = (type, props) => ({ type, props });
  const component = load(`src/pages/${page}.tsx`, {
    react,
    'react/jsx-runtime': { jsx, jsxs: jsx },
    'react-router-dom': { useParams: () => ({ id }), Link: 'a' },
    '../components/BolPdfViewer': { default: 'pdf-viewer' },
    ...Object.fromEntries(['billingRecord', 'correction', 'decision', 'validation',
      'recommendation', 'upload'].map(name => [`../api/${name}Api`, api])),
  }, { window: {
    setInterval(fn) { timers.set(++timer, fn); return timer; },
    clearInterval(handle) { timers.delete(handle); },
  }, URL: { createObjectURL: () => 'blob:preview', revokeObjectURL() {} } }).default;
  function render() {
    let count = 0;
    do {
      assert.ok(count++ < 20, 'render loop'); dirty = false; cursor = 0;
      tree = component(); const run = effects; effects = []; run.forEach(fn => fn());
    } while (dirty);
  }
  const find = predicate => { const node = nodes(tree).find(predicate); assert.ok(node, 'node found'); return node; };
  render();
  return {
    timers, render,
    async flush() { render(); await new Promise(setImmediate); render(); },
    input(key) { return find(n => n.type === 'input' && n.props.id === key).props; },
    button(label) { return find(n => n.type === 'button' && content(n) === label).props; },
    field(key) { return find(n => n.props?.className?.startsWith('review-field ') &&
      nodes(n).some(child => child.type === 'input' && child.props.id === key)).props; },
    text() { return content(tree); },
    documentLink() { return find(n => n.type === 'a' && n.props.className === 'review-document-link').props; },
    navigate(next) { id = next; render(); },
    unmount() { for (const slot of slots) slot.cleanup?.(); },
  };
}

test('Review polling merges OCR results, protects in-flight edits, and stops at completion', async () => {
  let response = billingRecord('UPLOADED'), calls = 0;
  const page = mount('ReviewPage', { getBillingRecord: async () => { calls++; return response; } });
  await page.flush(); assert.equal(page.timers.size, 1);
  page.input('carrier').onChange({ target: { value: 'Unsaved carrier' } }); page.render();
  const request = deferred(); response = request.promise;
  const tick = [...page.timers.values()][0]; const active = tick();
  await tick(); assert.equal(calls, 2, 'no overlapping polls');
  page.input('destination').onChange({ target: { value: 'Edit during request' } }); page.render();
  const finished = billingRecord('NEEDS_REVIEW'); finished.fields.supplier.normalizedValue = 'OCR supplier';
  request.resolve(finished); await active; page.render();
  assert.equal(page.input('carrier').value, 'Unsaved carrier');
  assert.equal(page.input('destination').value, 'Edit during request');
  assert.equal(page.input('supplier').value, 'OCR supplier');
  assert.equal(page.timers.size, 0); page.unmount();
});

test('late OCR response cannot replace a newly navigated review record', async () => {
  let response = billingRecord('OCR_PROCESSING');
  const page = mount('ReviewPage', { getBillingRecord: async () => response });
  await page.flush(); const request = deferred(); response = request.promise;
  const tick = [...page.timers.values()][0]();
  response = billingRecord('OCR_COMPLETE', 'rec-2'); page.navigate('rec-2'); await page.flush();
  request.resolve(billingRecord('OCR_COMPLETE')); await tick; page.render();
  assert.ok(page.text().includes('rec-2')); assert.equal(page.timers.size, 0); page.unmount();
});

test('saved missing-field corrections clear warnings without inventing confidence or raw values', async () => {
  const record = billingRecord(); const requests = [];
  const page = mount('ReviewPage', {
    getBillingRecord: async () => structuredClone(record),
    updateBillingField: async (...args) => {
      requests.push(args); const [, name, value] = args;
      Object.assign(record.fields[name], { normalizedValue: value, isCorrected: true });
      record.status = 'RECOMMENDATION_PENDING';
    },
    updateBillingLineItem: async (...args) => {
      requests.push(args); const [, , name, value] = args;
      Object.assign(record.lineItems[0][name], { normalizedValue: value, isCorrected: true });
    },
  });
  await page.flush();
  assert.ok(page.field('contractLifting').className.includes('warning'));
  assert.ok(page.field('line-line-1-e3StockId').className.includes('warning'));
  page.input('contractLifting').onChange({ target: { value: ' TEST-CONTRACT ' } });
  page.input('line-line-1-e3StockId').onChange({ target: { value: 'TEST-E3' } }); page.render();
  await page.button('Save Changes').onClick(); page.render();
  assert.deepEqual(requests, [['rec-1', 'contractLifting', 'TEST-CONTRACT'], ['rec-1', 'line-1', 'e3StockId', 'TEST-E3']]);
  assert.ok(!page.field('contractLifting').className.includes('warning'));
  assert.ok(!page.field('line-line-1-e3StockId').className.includes('warning'));
  assert.ok(page.text().includes('Unavailable')); assert.ok(page.text().includes('Original OCR: Not available'));
  assert.ok(page.text().includes('2 correction(s) saved')); assert.equal(page.button('Save Changes').disabled, true);
  page.unmount();
  const reloaded = mount('ReviewPage', { getBillingRecord: async () => structuredClone(record) });
  await reloaded.flush();
  assert.equal(reloaded.input('contractLifting').value, 'TEST-CONTRACT');
  assert.ok(!reloaded.field('contractLifting').className.includes('warning'));
  assert.ok(!reloaded.field('line-line-1-e3StockId').className.includes('warning'));
  assert.ok(reloaded.text().includes('Unavailable')); reloaded.unmount();
});

test('partial save keeps failed edits and confirms persisted numeric normalization', async () => {
  const record = billingRecord(); let fail = true;
  const page = mount('ReviewPage', {
    getBillingRecord: async () => structuredClone(record),
    updateBillingField: async (_, name, value) => { record.fields[name].normalizedValue = value; },
    updateBillingLineItem: async (_, line, name, value) => {
      if (fail) throw new Error('test failure');
      record.lineItems[0][name].normalizedValue = value;
    },
  });
  await page.flush();
  page.input('carrier').onChange({ target: { value: 'Reviewed' } });
  page.input('line-line-1-netGallons').onChange({ target: { value: ' 98.00 ' } }); page.render();
  await page.button('Save Changes').onClick(); page.render();
  assert.equal(page.input('carrier').value, 'Reviewed');
  assert.equal(page.input('line-line-1-netGallons').value, ' 98.00 ');
  assert.ok(page.text().includes('Saved 1/2')); fail = false;
  await page.button('Save Changes').onClick(); page.render();
  assert.equal(page.input('line-line-1-netGallons').value, '98');
  assert.equal(page.button('Save Changes').disabled, true); page.unmount();
});

test('UploadPage polls until OCR completes', async () => {
  let record = billingRecord('UPLOADED'), calls = 0;
  const page = mount('UploadPage', {
    uploadBillingRecord: async () => ({ recordId: 'rec-1' }),
    getBillingRecord: async () => { calls++; return record; },
  });
  page.input('bol-file').onChange({ target: { files: [{ name: 'sample.pdf', type: 'application/pdf', size: 100 }] } });
  page.render(); await page.button('Upload & Process BOL').onClick(); await page.flush();
  assert.equal(page.timers.size, 1); assert.ok(page.text().includes('OCR is still processing'));
  const pending = deferred(); record = pending.promise;
  const tick = [...page.timers.values()][0]; const active = tick(); await tick(); assert.equal(calls, 2);
  pending.resolve(billingRecord('OCR_COMPLETE')); await active; page.render();
  assert.equal(page.timers.size, 0); assert.ok(page.text().includes('BOL processed and saved'));
  page.unmount();
});

test('correction API helpers send value-only PATCH requests with session and CSRF', async () => {
  const requests = [];
  const api = load('src/api/apiClient.ts', {}, { Headers, FormData, fetch: async (url, options) => {
    requests.push({url, options});
    return { ok: true, status: 200, json: async () => url.endsWith('/csrf/') ? { csrfToken: 'test-token' } : {} };
  }});
  const corrections = load('src/api/correctionApi.ts', { './apiClient': api });
  await corrections.updateBillingField('rec/a', 'contractLifting', 'TEST');
  await corrections.updateBillingLineItem('rec/a', 'line/b', 'e3StockId', 'TEST-E3');
  const patches = requests.filter(r => r.options.method === 'PATCH'); assert.equal(patches.length, 2);
  assert.equal(patches[0].url, '/api/v1/billing-records/rec%2Fa/fields/contractLifting/');
  assert.equal(patches[1].url, '/api/v1/billing-records/rec%2Fa/line-items/line%2Fb/e3StockId/');
  assert.equal(patches[0].options.body, '{"value":"TEST"}');
  for (const { options } of patches) {
    assert.equal(options.credentials, 'include'); assert.equal(options.headers.get('X-CSRFToken'), 'test-token');
  }
});


test('UploadPage discards an in-flight poll after a new file selection', async () => {
  let response = billingRecord('UPLOADED');
  const page = mount('UploadPage', {
    uploadBillingRecord: async () => ({ recordId: 'rec-1' }),
    getBillingRecord: async () => response,
  });
  const selection = name => ({ target: { files: [{ name, type: 'application/pdf', size: 100 }] } });
  page.input('bol-file').onChange(selection('first.pdf')); page.render();
  await page.button('Upload & Process BOL').onClick(); await page.flush();
  const request = deferred(); response = request.promise;
  const active = [...page.timers.values()][0]();
  page.input('bol-file').onChange(selection('second.pdf')); page.render();
  request.resolve(billingRecord('OCR_COMPLETE')); await active; page.render();
  assert.equal(page.timers.size, 0);
  assert.ok(page.text().includes('second.pdf')); assert.ok(!page.text().includes('rec-1'));
  page.unmount();
});

test('failed refresh after PATCH retains edits and does not claim a verified save', async () => {
  let calls = 0;
  const page = mount('ReviewPage', {
    getBillingRecord: async () => { if (calls++) throw new Error('offline'); return billingRecord(); },
    updateBillingField: async () => ({}),
  });
  await page.flush();
  page.input('carrier').onChange({ target: { value: 'Unsure if saved' } }); page.render();
  await page.button('Save Changes').onClick(); page.render();
  assert.equal(page.input('carrier').value, 'Unsure if saved');
  assert.ok(page.text().includes('refreshing the record failed'));
  assert.ok(!page.text().includes('saved and confirmed')); page.unmount();
});


test('failed OCR shows its cause in Review Workspace and prevents empty corrections', async () => {
  const record = billingRecord('EXCEPTION');
  record.ocrJob = { jobId: 'job-1', status: 'FAILED', errorCode: 'OCR_FAILED', errorMessage: 'OCR could not read this document.' };
  const page = mount('ReviewPage', { getBillingRecord: async () => record });
  await page.flush();
  assert.ok(page.text().includes('OCR failed: OCR could not read this document.'));
  assert.equal(page.input('carrier').disabled, true);
  assert.equal(page.button('Save Changes').disabled, true);
  page.unmount();
});

test('failed OCR upload displays its stored error instead of a success message', async () => {
  const record = billingRecord('EXCEPTION');
  record.ocrJob = { jobId: 'job-1', status: 'FAILED', errorCode: 'OCR_FAILED', errorMessage: 'Provider could not complete OCR.' };
  const page = mount('UploadPage', {
    uploadBillingRecord: async () => ({ recordId: 'rec-1' }),
    getBillingRecord: async () => record,
  });
  page.input('bol-file').onChange({ target: { files: [{ name: 'sample.pdf', type: 'application/pdf', size: 100 }] } });
  page.render(); await page.button('Upload & Process BOL').onClick(); await page.flush();
  assert.ok(page.text().includes('OCR failed: Provider could not complete OCR.'));
  assert.ok(!page.text().includes('BOL processed and saved by the backend successfully.'));
  page.unmount();
});


test('review document URLs stay on the public frontend origin', async () => {
  for (const url of ['/media/bols/source.pdf', 'http://127.0.0.1:8000/media/bols/source.pdf', 'http://localhost:8000/media/bols/source.pdf']) {
    const record = billingRecord(); record.document = { documentUrl: url, originalFilename: 'source.pdf' };
    const page = mount('ReviewPage', { getBillingRecord: async () => record });
    await page.flush();
    assert.equal(page.documentLink().href, '/media/bols/source.pdf');
    page.unmount();
  }
});

test('legacy loopback API configuration uses the public origin for CSRF and multipart upload', async () => {
  for (const base of ['http://localhost:8000/api/v1/', 'http://127.0.0.1:8000/api/v1', 'http://[::1]:8000/api/v1']) {
    const calls = [];
    const api = load('src/api/apiClient.ts', {}, {
      __API_BASE_URL__: base, Headers, FormData,
      fetch: async (url, options) => {
        calls.push({url, options});
        return { ok: true, status: 200, json: async () => url.endsWith('/csrf/')
          ? { csrfToken: 'test-token' } : { recordId: 'rec-1' } };
      },
    });
    const upload = load('src/api/uploadApi.ts', { './apiClient': api }, { FormData });
    await upload.uploadBillingRecord(new Blob(['test']));
    assert.deepEqual(calls.map(c => c.url), ['/api/v1/auth/csrf/', '/api/v1/billing-records/upload/']);
    assert.equal(calls[0].options.cache, 'no-store');
    assert.equal(calls[1].options.headers.has('Content-Type'), false, 'browser supplies the multipart boundary');
    assert.equal(calls[1].options.headers.get('X-CSRFToken'), 'test-token');
    assert.equal(calls[1].options.credentials, 'include');
  }
});

test('a stalled CSRF request times out before sending the upload', async () => {
  const timers = new Map(), calls = [];
  const api = load('src/api/apiClient.ts', {}, { Headers, FormData,
    setTimeout(fn, ms) { timers.set(ms, fn); return ms; },
    clearTimeout(ms) { timers.delete(ms); },
    fetch: (url, { signal }) => {
      calls.push(url);
      return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))));
    },
  });
  const request = api.apiRequest('/billing-records/upload/', { method: 'POST', body: new FormData() });
  const rejected = assert.rejects(request, /within 15 seconds.*request has not been sent/);
  timers.get(15000)(); await rejected;
  assert.deepEqual(calls, ['/api/v1/auth/csrf/']); assert.equal(timers.size, 0);
});

test('a stalled upload response body times out without retrying an uncertain save', async () => {
  const timers = new Map(), calls = [];
  const api = load('src/api/apiClient.ts', {}, { Headers, FormData,
    setTimeout(fn, ms) { timers.set(ms, fn); return ms; },
    clearTimeout(ms) { timers.delete(ms); },
    fetch: async (url, { signal }) => {
      calls.push(url);
      return { ok: true, status: 200, json: () => url.endsWith('/csrf/')
        ? Promise.resolve({ csrfToken: 'test-token' })
        : new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')))) };
    },
  });
  const request = api.apiRequest('/billing-records/upload/', { method: 'POST', body: new FormData(), timeoutMs: 60000 });
  const rejected = assert.rejects(request, /may already be saved.*Check the Dashboard/);
  await new Promise(setImmediate); timers.get(60000)(); await rejected;
  assert.equal(calls.length, 2); assert.equal(timers.size, 0);
});

test('upload receipt opens Review immediately while detail loading stalls, then recovers without another POST', async () => {
  const pending = deferred(); let uploads = 0, response = pending.promise;
  const page = mount('UploadPage', {
    uploadBillingRecord: async () => { uploads++; return { recordId: 'rec-1', status: 'UPLOADED' }; },
    getBillingRecord: async () => response,
  });
  page.input('bol-file').onChange({ target: { files: [{ name: 'test.pdf', type: 'application/pdf', size: 100 }] } });
  page.render(); await page.button('Upload & Process BOL').onClick(); await page.flush();
  assert.ok(page.text().includes('Billing record saved successfully'));
  assert.ok(page.text().includes('Review Document →'));
  assert.ok(!page.text().includes('Uploading BOL'));
  assert.equal(page.button('Upload & Process BOL').disabled, true);
  pending.resolve(Promise.reject(new Error('detail request timed out'))); await page.flush();
  assert.ok(page.text().includes('Your file is saved, but its latest OCR status could not be loaded'));
  response = billingRecord('NEEDS_REVIEW');
  await [...page.timers.values()][0](); page.render();
  assert.ok(page.text().includes('BOL processed and saved'));
  assert.ok(!page.text().includes('could not be loaded'));
  assert.equal(uploads, 1); assert.equal(page.timers.size, 0); page.unmount();
});

test('a late upload response does not replace a newly selected file', async () => {
  const pending = deferred(); let details = 0;
  const page = mount('UploadPage', {
    uploadBillingRecord: () => pending.promise,
    getBillingRecord: async () => { details++; return billingRecord(); },
  });
  const selection = name => ({ target: { files: [{ name, type: 'application/pdf', size: 100 }] } });
  page.input('bol-file').onChange(selection('first.pdf')); page.render();
  const upload = page.button('Upload & Process BOL').onClick(); page.render();
  page.input('bol-file').onChange(selection('second.pdf')); page.render();
  pending.resolve({ recordId: 'rec-1', status: 'UPLOADED' }); await upload; await page.flush();
  assert.ok(page.text().includes('second.pdf'));
  assert.ok(!page.text().includes('Billing record saved successfully'));
  assert.equal(details, 0); assert.equal(page.timers.size, 0); page.unmount();
});

function testRecommendation() {
  return { recommendation: 'REVIEW_REQUIRED', confidence: null,
    rationale: 'Test fixture: reviewer must check the mapping.', modelVersion: 'test-rules-v1',
    matchedTerminalLogId: null,
    mappedEntities: { carrierCode: 'TEST-CARRIER', lineItems: [
      { lineItemId: 'line-1', e3StockId: 'TEST-E3', standardName: 'Test mapped product' },
    ] },
    exceptionIndicators: [{ code: 'TEST_MAPPING', severity: 'WARNING', message: 'Test mapping warning.' }],
  };
}

test('saved Team A recommendation populates the detailed panel after page reload without evaluation', async () => {
  const record = billingRecord('RECOMMENDATION_READY');
  record.recommendation = testRecommendation(); let evaluations = 0;
  for (let reload = 0; reload < 2; reload++) {
    const page = mount('ReviewPage', {
      getBillingRecord: async () => structuredClone(record),
      evaluateBillingRecord: async () => { evaluations++; throw new Error('must not evaluate on load'); },
    });
    await page.flush();
    for (const value of ['REVIEW REQUIRED', 'test-rules-v1', 'TEST-CARRIER', 'TEST-E3',
      'Test mapped product', 'Test mapping warning.', 'Unavailable']) assert.ok(page.text().includes(value), value);
    assert.equal(page.button('Refresh Recommendation').disabled, false); page.unmount();
  }
  assert.equal(evaluations, 0);
});

test('Get Recommendation submits once, shows the result, and preserves edits made during evaluation', async () => {
  const pending = deferred(); const calls = []; const record = billingRecord('NEEDS_REVIEW');
  const page = mount('ReviewPage', {
    getBillingRecord: async () => structuredClone(record),
    evaluateBillingRecord: async id => { calls.push(id); return pending.promise; },
  });
  await page.flush();
  const request = page.button('Get Recommendation').onClick(); page.render();
  assert.equal(page.button('Refreshing...').disabled, true);
  page.input('carrier').onChange({ target: { value: 'Unsaved during evaluation' } }); page.render();
  assert.equal(page.button('Save Changes').disabled, true);
  Object.assign(record, { status: 'RECOMMENDATION_READY', recommendation: testRecommendation() });
  pending.resolve({ recordId: 'rec-1', status: record.status, pending: false, recommendation: record.recommendation });
  await request; page.render();
  assert.deepEqual(calls, ['rec-1']);
  assert.ok(page.text().includes('Test mapped product'));
  assert.equal(page.input('carrier').value, 'Unsaved during evaluation');
  assert.equal(page.button('Refresh Recommendation').disabled, true, 'save unsaved edits before another evaluation');
  page.unmount();
});

test('a late evaluation response cannot populate another review record', async () => {
  const pending = deferred(); let record = billingRecord('NEEDS_REVIEW');
  const page = mount('ReviewPage', {
    getBillingRecord: async () => record,
    evaluateBillingRecord: () => pending.promise,
  });
  await page.flush(); const request = page.button('Get Recommendation').onClick(); page.render();
  record = billingRecord('NEEDS_REVIEW', 'rec-2'); page.navigate('rec-2'); await page.flush();
  pending.resolve({ recordId: 'rec-1', status: 'RECOMMENDATION_READY', pending: false, recommendation: testRecommendation() });
  await request; page.render();
  assert.ok(page.text().includes('rec-2')); assert.ok(!page.text().includes('Test mapped product'));
  assert.equal(page.button('Get Recommendation').disabled, false); page.unmount();
});

test('retryable Team A response shows the backend cause and does not invent a recommendation or retry', async () => {
  const record = billingRecord('NEEDS_REVIEW'); let calls = 0;
  const page = mount('ReviewPage', {
    getBillingRecord: async () => structuredClone(record),
    evaluateBillingRecord: async () => {
      calls++; record.status = 'RECOMMENDATION_PENDING';
      return { recordId: 'rec-1', status: record.status, pending: true,
        error: { code: 'TEAM_A_UNAVAILABLE', message: 'Test service unavailable.', retryable: true } };
    },
  });
  await page.flush(); await page.button('Get Recommendation').onClick(); page.render();
  assert.ok(page.text().includes('Test service unavailable.'));
  assert.ok(page.text().includes('not returned a completed recommendation'));
  assert.equal(calls, 1); assert.equal(page.timers.size, 0); page.unmount();
});

test('evaluation result stays visible if its follow-up GET fails, with a verification warning', async () => {
  let reads = 0;
  const page = mount('ReviewPage', {
    getBillingRecord: async () => { if (reads++) throw new Error('offline'); return billingRecord('NEEDS_REVIEW'); },
    evaluateBillingRecord: async () => ({ recordId: 'rec-1', status: 'RECOMMENDATION_READY', pending: false, recommendation: testRecommendation() }),
  });
  await page.flush(); await page.button('Get Recommendation').onClick(); page.render();
  assert.ok(page.text().includes('Test mapped product'));
  assert.ok(page.text().includes('reloading the saved record failed'));
  page.unmount();
});

test('recommendation action respects OCR and final workflow states', async () => {
  for (const status of ['UPLOADED', 'OCR_PROCESSING', 'EXCEPTION', 'APPROVED', 'REJECTED']) {
    let calls = 0;
    const page = mount('ReviewPage', {
      getBillingRecord: async () => billingRecord(status),
      evaluateBillingRecord: async () => { calls++; },
    });
    await page.flush();
    assert.equal(page.button('Get Recommendation').disabled, true);
    await page.button('Get Recommendation').onClick(); assert.equal(calls, 0); page.unmount();
  }
});

test('recommendation API uses the authenticated Team B endpoint and waits for its existing retry window', async () => {
  const calls = [], timeouts = [];
  const api = load('src/api/apiClient.ts', {}, { Headers, FormData,
    setTimeout(fn, ms) { timeouts.push(ms); return ms; }, clearTimeout() {},
    fetch: async (url, options) => {
      calls.push({ url, options });
      return { ok: true, status: 200, json: async () => url.endsWith('/csrf/')
        ? { csrfToken: 'test-token' } : { recordId: 'rec/1', status: 'RECOMMENDATION_READY', pending: false, recommendation: testRecommendation() } };
    },
  });
  const recommendations = load('src/api/recommendationApi.ts', { './apiClient': api });
  const result = await recommendations.evaluateBillingRecord('rec/1');
  assert.equal(result.recommendation.modelVersion, 'test-rules-v1');
  assert.equal(calls[1].url, '/api/v1/billing-records/rec%2F1/evaluate/');
  assert.equal(calls[1].options.method, 'POST'); assert.equal(calls[1].options.credentials, 'include');
  assert.equal(calls[1].options.headers.get('X-CSRFToken'), 'test-token');
  assert.equal(calls[1].options.headers.has('X-API-Key'), false);
  assert.deepEqual(timeouts, [15000, 150000]);
});
