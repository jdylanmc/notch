const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const workflowRoot = path.resolve(__dirname, '../workflows');
const marker = '<!-- fork-pr-target-policy -->';

function workflow(name) {
  return readFileSync(path.join(workflowRoot, name), 'utf8');
}

function inlineScript(name) {
  const lines = workflow(name).split(/\r?\n/);
  const starts = lines.flatMap((line, index) => /^\s+script: \|$/.test(line) ? [index] : []);
  assert.equal(starts.length, 1, `${name} must contain one inline policy script`);
  const start = starts[0];
  const indent = lines[start].match(/^\s*/)[0].length + 2;
  const body = [];
  for (const line of lines.slice(start + 1)) {
    if (line.trim() && !line.startsWith(' '.repeat(indent))) break;
    body.push(line.slice(indent));
  }
  assert.ok(body.join('\n').trim(), `${name} policy script must not be empty`);
  return body.join('\n');
}

async function runPolicy(name, {
  base = 'pocket',
  latestBase = base,
  isFork = true,
  comments = [],
  readError,
} = {}) {
  const result = { failures: [], messages: [], writes: [], reads: [] };
  const listComments = () => {};
  const pr = {
    number: 55,
    base: { ref: base },
    head: { repo: { fork: isFork, full_name: 'jdylanmc/notch' } },
  };
  const github = {
    rest: {
      pulls: {
        get: async () => {
          result.reads.push('pull');
          if (readError) throw readError;
          return { data: { ...pr, base: { ref: latestBase } } };
        },
      },
      issues: {
        listComments,
        createComment: async (args) => result.writes.push({ action: 'create', ...args }),
        updateComment: async (args) => result.writes.push({ action: 'update', ...args }),
        deleteComment: async (args) => result.writes.push({ action: 'delete', ...args }),
      },
    },
    paginate: async (method) => {
      assert.equal(method, listComments, 'Target policy must not depend on changed-file allowlists');
      result.reads.push('comments');
      return comments;
    },
  };
  const script = new vm.Script(`(async () => {\n${inlineScript(name)}\n})()`, { filename: name });
  await script.runInNewContext({
    context: { payload: { pull_request: pr }, repo: { owner: 'jdylanmc', repo: 'notch' } },
    github,
    core: {
      info: (message) => result.messages.push(message),
      setFailed: (message) => result.failures.push(message),
    },
  }, { timeout: 1000 });
  return result;
}

for (const name of ['base_ref_check.yml', 'base_ref_check_comment.yml']) {
  test(`${name}: applies regardless of repository fork metadata without checking out PR code`, () => {
    const source = workflow(name);
    assert.doesNotMatch(source, /head\.repo\.fork/);
    assert.doesNotMatch(source, /actions\/checkout/);
    assert.doesNotMatch(source, /secrets\./);
    assert.match(source, /pull_request_target:/);
    assert.match(source, /^permissions: \{\}$/m);
  });
}

for (const isFork of [true, false]) {
  test(`accept pocket when head.repo.fork is ${isFork}`, async () => {
    const result = await runPolicy('base_ref_check.yml', { isFork });
    assert.deepEqual(result.failures, []);
    assert.deepEqual(result.reads, []);
    assert.match(result.messages.join('\n'), /pocket.*allowed/i);
  });
}

for (const base of ['dev', 'main', 'release', 'Pocket', 'pocket/preview']) {
  test(`reject ${base} without a metadata-only exception`, async () => {
    const result = await runPolicy('base_ref_check.yml', { base });
    assert.equal(result.failures.length, 1);
    assert.match(result.failures[0], /must target "pocket"/);
    assert.deepEqual(result.reads, []);
  });
}

test('preserve the existing required-check context', () => {
  assert.match(workflow('base_ref_check.yml'), /name: Fork PR target check/);
});

test('escape branch names in failure messages', async () => {
  const result = await runPolicy('base_ref_check.yml', { base: '<x>@everyone#1`bad\u202E' });
  assert.equal(result.failures.length, 1);
  assert.doesNotMatch(result.failures[0], /<x>|@everyone|#1|`|\u202E/);
  assert.match(result.failures[0], /\\u202e/i);
});

test('valid pocket PR needs no guidance comment', async () => {
  const result = await runPolicy('base_ref_check_comment.yml', { isFork: false });
  assert.deepEqual(result.writes, []);
  assert.deepEqual(result.reads, ['pull', 'comments']);
});

for (const base of ['dev', 'main', 'release']) {
  test(`create pocket guidance for ${base}, including same-repository PRs`, async () => {
    const result = await runPolicy('base_ref_check_comment.yml', { base, isFork: false });
    assert.equal(result.writes.length, 1);
    assert.equal(result.writes[0].action, 'create');
    assert.equal(result.writes[0].issue_number, 55);
    assert.ok(result.writes[0].body.includes(marker));
    assert.match(result.writes[0].body, /must target `pocket`/);
    assert.doesNotMatch(result.writes[0].body, /retarget.*(?:dev|main)/i);
  });
}

test('delete the old upstream guidance after a PR targets pocket', async () => {
  const result = await runPolicy('base_ref_check_comment.yml', {
    comments: [{ id: 42, user: { login: 'github-actions[bot]' }, body: `${marker}\nPlease target dev.` }],
  });
  assert.deepEqual(result.writes.map(({ action, comment_id }) => ({ action, comment_id })), [
    { action: 'delete', comment_id: 42 },
  ]);
});

test('use the current PR target rather than a stale event target', async () => {
  const result = await runPolicy('base_ref_check_comment.yml', { base: 'main', latestBase: 'pocket' });
  assert.deepEqual(result.writes, []);
});

test('update existing bot guidance instead of creating another comment', async () => {
  const result = await runPolicy('base_ref_check_comment.yml', {
    base: 'dev',
    comments: [{ id: 42, user: { login: 'github-actions[bot]' }, body: `${marker}\nTarget main.` }],
  });
  assert.equal(result.writes.length, 1);
  assert.equal(result.writes[0].action, 'update');
  assert.equal(result.writes[0].comment_id, 42);
  assert.match(result.writes[0].body, /must target `pocket`/);
});

test('matching guidance is idempotent', async () => {
  const first = await runPolicy('base_ref_check_comment.yml', { base: 'dev' });
  const second = await runPolicy('base_ref_check_comment.yml', {
    base: 'dev',
    comments: [{ id: 42, user: { login: 'github-actions[bot]' }, body: first.writes[0].body }],
  });
  assert.deepEqual(second.writes, []);
});

test('never modify a human comment containing the policy marker', async () => {
  const comment = { id: 42, user: { login: 'contributor' }, body: marker };
  const valid = await runPolicy('base_ref_check_comment.yml', { comments: [comment] });
  assert.deepEqual(valid.writes, []);
  const invalid = await runPolicy('base_ref_check_comment.yml', { base: 'dev', comments: [comment] });
  assert.equal(invalid.writes[0].action, 'create');
});

test('escape branch names in guidance comments', async () => {
  const result = await runPolicy('base_ref_check_comment.yml', { base: '<x>@everyone#1`bad\u202E' });
  assert.equal(result.writes.length, 1);
  assert.doesNotMatch(result.writes[0].body, /<x>|@everyone|#1|\u202E/);
  assert.match(result.writes[0].body, /\\u202e/i);
});

test('surface API failures instead of reporting successful guidance sync', async () => {
  await assert.rejects(
    runPolicy('base_ref_check_comment.yml', { readError: new Error('permission denied') }),
    /permission denied/,
  );
});
