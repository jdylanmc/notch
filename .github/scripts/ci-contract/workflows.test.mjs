import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import test from 'node:test';
import { parseDocument } from 'yaml';

const root = new URL('../../../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
const checkout = 'actions/checkout';
const xcodebuild = 'mxcl/xcodebuild';
const codeql = 'github/codeql-action';
const helper = 'bash scripts/notch-control/control.sh';
const install = 'npm ci --prefix .github/scripts/ci-contract --ignore-scripts --no-audit --no-fund';

function parse(source) {
  const document = parseDocument(source, { version: '1.2', strict: true, uniqueKeys: true });
  assert.deepEqual(document.errors, [], 'YAML must be valid and have unique mapping keys');
  const value = document.toJS();
  assert.ok(value && typeof value === 'object' && !Array.isArray(value), 'Expected a YAML mapping');
  return value;
}

const workflow = (name) => parse(read(`.github/workflows/${name}.yml`));
const step = (job, name) => {
  const matches = job.steps.filter((entry) => entry.name === name);
  assert.equal(matches.length, 1, `Expected exactly one ${name} step`);
  return matches[0];
};

function pinnedAction(job, name, repository) {
  const { uses } = step(job, name);
  assert.equal(typeof uses, 'string', `${name}: expected an action`);
  const [identity, commit] = uses.split('@');
  assert.equal(identity, repository, `${name}: expected action repository/subpath`);
  assert.match(commit ?? '', /^[a-fA-F0-9]{40}$/, `${name}: expected an immutable full SHA`);
  assert.equal(uses, `${repository}@${commit}`);
  return uses;
}

function productTriggers(config, scheduled = false) {
  assert.deepEqual(Object.keys(config.on).sort(), scheduled
    ? ['pull_request', 'push', 'schedule'] : ['pull_request', 'push']);
  for (const event of ['push', 'pull_request']) {
    assert.deepEqual(config.on[event], { branches: ['pocket'] }, `${event}: pocket only, no path filters`);
    assert.ok(config.on[event].branches.includes('pocket'));
    for (const branch of ['main', 'dev', 'stack/preview', 'feature/example', 'pocket/preview']) {
      assert.ok(!config.on[event].branches.includes(branch), `${event}: reject ${branch}`);
    }
  }
  if (scheduled) assert.deepEqual(config.on.schedule, [{ cron: '31 15 * * 1' }]);
}

function appContract(config) {
  productTriggers(config);
  assert.equal(config.name, 'Build for macOS');
  assert.deepEqual(config.permissions, { contents: 'read' });
  assert.deepEqual(config.concurrency, {
    group: '${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}',
    'cancel-in-progress': true,
  });
  assert.deepEqual(Object.keys(config.jobs), ['build']);
  const job = config.jobs.build;
  assert.equal(job.name, 'Build Notch Pocket (${{ matrix.xcode }} on ${{ matrix.os }})');
  assert.equal(job['runs-on'], '${{ matrix.os }}');
  assert.deepEqual(job.strategy, {
    'fail-fast': false,
    matrix: { include: [
      { os: 'macos-15', xcode: '~26.0' },
      { os: 'macos-26', xcode: '^26' },
      { os: 'xcode-27', xcode: '^27' },
    ] },
  });
  assert.equal(job.if, undefined);
  assert.equal(job['continue-on-error'], undefined);
  assert.deepEqual(job.steps, [
    { name: 'Checkout', uses: pinnedAction(job, 'Checkout', checkout) },
    ...[['Build', 'build', 'release'], ['Test', 'test', 'debug']].map(([name, action, configuration]) => ({
      name, uses: pinnedAction(job, name, xcodebuild), with: {
        xcode: '${{ matrix.xcode }}', platform: 'macOS', scheme: 'notchPocket',
        action, verbosity: 'xcpretty', 'upload-logs': 'always', configuration,
      },
    })),
  ]);
}

function lintContract(config) {
  productTriggers(config);
  assert.equal(config.name, 'SwiftLint');
  assert.deepEqual(config.permissions, { contents: 'read' });
  assert.deepEqual(config.concurrency, {
    group: '${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}',
    'cancel-in-progress': true,
  });
  assert.deepEqual(config.jobs, { swiftlint: {
    name: 'SwiftLint', 'runs-on': 'macos-26',
    steps: [
      { name: 'Checkout', uses: pinnedAction(config.jobs.swiftlint, 'Checkout', checkout), with: { 'persist-credentials': false } },
      { name: 'Install SwiftLint', run: 'which swiftlint || brew install swiftlint' },
      { name: 'Run SwiftLint', run: 'swiftlint --config .swiftlint.yml' },
    ],
  } });
}

function codeqlContract(config) {
  productTriggers(config, true);
  assert.equal(config.name, 'CodeQL Advanced');
  assert.equal(config.permissions, undefined);
  assert.deepEqual(Object.keys(config.jobs), ['analyze']);
  const job = config.jobs.analyze;
  assert.equal(job.name, 'Analyze (${{ matrix.language }})');
  assert.equal(job['runs-on'], "${{ (matrix.language == 'swift' && 'xcode-27') || 'ubuntu-latest' }}");
  assert.deepEqual(job.permissions, {
    'security-events': 'write', packages: 'read', actions: 'read', contents: 'read',
  });
  assert.deepEqual(job.strategy, { 'fail-fast': false, matrix: { include: [
    { language: 'actions', 'build-mode': 'none' },
    { language: 'python', 'build-mode': 'none' },
    { language: 'swift', 'build-mode': 'manual' },
  ] } });
  assert.equal(job.if, undefined);
  assert.equal(job['continue-on-error'], undefined);
  assert.deepEqual(job.steps.map(({ name }) => name), [
    'Checkout repository', 'Resolve Swift package dependencies', 'Initialize CodeQL',
    'Build Notch Pocket', 'Build notch-control', 'Perform CodeQL Analysis',
  ]);
  assert.deepEqual(step(job, 'Checkout repository'), {
    name: 'Checkout repository', uses: pinnedAction(job, 'Checkout repository', checkout), with: { 'persist-credentials': false },
  });
  assert.equal(step(job, 'Resolve Swift package dependencies').if, "matrix.language == 'swift'");
  const init = pinnedAction(job, 'Initialize CodeQL', `${codeql}/init`);
  const analyze = pinnedAction(job, 'Perform CodeQL Analysis', `${codeql}/analyze`);
  assert.equal(init.split('@')[1], analyze.split('@')[1], 'CodeQL init/analyze must use the same SHA');
  assert.deepEqual(step(job, 'Initialize CodeQL'), {
    name: 'Initialize CodeQL', uses: init,
    with: { languages: '${{ matrix.language }}', 'build-mode': '${{ matrix.build-mode }}' },
  });
  assert.deepEqual(step(job, 'Perform CodeQL Analysis'), {
    name: 'Perform CodeQL Analysis', uses: analyze,
    with: { category: '/language:${{matrix.language}}' },
  });
  const app = step(job, 'Build Notch Pocket');
  assert.deepEqual(Object.keys(app).sort(), ['if', 'name', 'run']);
  assert.equal(app.if, "matrix.language == 'swift'");
  for (const fragment of [
    'set -o pipefail', 'xcodebuild', '-project notchPocket.xcodeproj', '-scheme notchPocket',
    '-configuration Release', '-destination "platform=macOS"',
    '-derivedDataPath "$RUNNER_TEMP/notchPocket-derived-data"',
    '-clonedSourcePackagesDirPath "$RUNNER_TEMP/notchPocket-source-packages"',
    '-onlyUsePackageVersionsFromResolvedFile', 'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO',
  ]) assert.ok(app.run.includes(fragment), `App extraction retains ${fragment}`);
  assert.match(app.run, /\n\s+build\s*$/);
  assert.deepEqual(step(job, 'Build notch-control'), {
    name: 'Build notch-control', if: "matrix.language == 'swift'", run: `${helper} build`,
  });
}

function hostedContract(config, kind) {
  productTriggers(config);
  assert.deepEqual(config.permissions, { contents: 'read' });
  const isHelper = kind === 'helper';
  assert.equal(config.name, isHelper ? 'notch-control' : 'CI contract tests');
  assert.deepEqual(config.jobs, {
    [isHelper ? 'validate' : 'test']: {
      name: isHelper ? 'Build, test, lint notch-control' : 'Test product CI contracts',
      'runs-on': isHelper ? 'macos-26' : 'ubuntu-latest',
      'timeout-minutes': isHelper ? 20 : 5,
      steps: [
        {
          name: 'Checkout',
          uses: pinnedAction(config.jobs[isHelper ? 'validate' : 'test'], 'Checkout', checkout),
          with: { 'persist-credentials': false },
        },
        ...(isHelper ? [
          { name: 'Install SwiftLint', run: 'which swiftlint || brew install swiftlint' },
          { name: 'Build helper', run: `${helper} build` },
          { name: 'Test helper', run: `${helper} test` },
          { name: 'Lint helper', run: `${helper} lint` },
        ] : [
          { name: 'Install contract test dependency', run: install },
          { name: 'Test workflow contracts', run: 'npm test --prefix .github/scripts/ci-contract' },
          { name: 'Test PR target policy', run: 'node --test .github/scripts/pr-target-policy.test.cjs' },
          { name: 'Test local packaging policy', run: "python3 -B -m unittest discover -s scripts/tests -p 'test_package.py'" },
        ]),
      ],
    },
  });
  assert.equal(config.env, undefined);
  assert.equal(config.defaults, undefined);
}

function packagingContract(reusable, release) {
  assert.equal(reusable.jobs.build.env.PROJECT_NAME, 'notchPocket');
  assert.equal(reusable.jobs.build.env.APP_PRODUCT_NAME, 'notch-pocket');
  assert.equal(release.env.PROJECT_NAME, 'notchPocket');
  assert.equal(release.env.APP_PRODUCT_NAME, 'notch-pocket');
  const archive = step(reusable.jobs.build, 'Build and archive').run;
  assert.ok(archive.includes('-project ${{ env.PROJECT_NAME }}.xcodeproj'));
  assert.ok(archive.includes('-scheme ${{ env.PROJECT_NAME }}'));
  const dmg = step(reusable.jobs.build, 'Create DMG').run;
  assert.ok(dmg.includes('"Release/${{ env.APP_PRODUCT_NAME }}.app"'));
  assert.ok(dmg.includes('"Release/${{ env.APP_PRODUCT_NAME }}.dmg"'));
  for (const [name, extension] of [['Upload DMG', 'dmg'], ['Upload .app', 'app']]) {
    assert.deepEqual(step(reusable.jobs.build, name).with, {
      name: `\${{ env.APP_PRODUCT_NAME }}.${extension}`,
      path: `Release/\${{ env.APP_PRODUCT_NAME }}.${extension}`,
    });
  }
  const download = release.jobs.publish.steps.find(({ uses }) => uses?.startsWith('actions/download-artifact@'));
  assert.deepEqual(download.with, { name: '${{ env.APP_PRODUCT_NAME }}.dmg', path: 'Release' });
  assert.ok(step(release.jobs.publish, 'Create GitHub release').run.includes('Release/notch-pocket.dmg'));
}

const swiftTestInvocation = 'xcrun swift test "${common[@]}" >&2 || fail "Native tool tests failed."';
const swiftBuildInvocation = 'xcrun swift build "${common[@]}" --product notch-control >&2 || fail "Native tool build failed."';
const testExecutableExport = 'export NOTCH_CONTROL_TEST_EXECUTABLE="$cache/products/debug/notch-control"';
const commonDefinition = [
  'common=(--package-path "$root" --scratch-path "$cache/products"',
  '--cache-path "$cache/cache" --config-path "$cache/config" --security-path "$cache/security")',
];
const shellLines = (source) => source.split('\n').map((line) => line.trim()).filter(Boolean);
const launcherArm = (source, mode) =>
  shellLines(source.match(new RegExp(`^\\s*${mode}\\)\\s*\\n([\\s\\S]*?)^\\s*;;`, 'm'))?.[1] ?? '');

function launcherTestContract(source) {
  const lines = shellLines(source);
  // Target the declared launcher shape, not arbitrary Bash semantics; ignore indentation/blank lines.
  const definitionIndex = lines.indexOf(commonDefinition[0]);
  assert.ok(definitionIndex >= 0 && definitionIndex < lines.indexOf('case "$mode" in'));
  assert.deepEqual(lines.slice(definitionIndex, definitionIndex + 2), commonDefinition,
    'Shared Swift arguments remain fixed and unfiltered');
  assert.deepEqual(lines.filter((line) => /\bcommon\b/.test(line)),
    [commonDefinition[0], swiftBuildInvocation, swiftBuildInvocation, swiftTestInvocation],
    'Shared arguments have only the canonical definition and build/test uses, with no mutations');
  const invocations = lines.filter((line) => /^xcrun swift test\b/.test(line));
  assert.deepEqual(invocations, [swiftTestInvocation], 'Launcher retains the complete unfiltered Swift test line');
  assert.deepEqual(launcherArm(source, 'test'), [
    '[[ $# -eq 0 ]] || fail "test takes no arguments."',
    'export NOTCH_CONTROL_TEST_ROOT="$cache"',
    swiftBuildInvocation,
    testExecutableExport,
    swiftTestInvocation,
    String.raw`printf '{"ok":true,"command":"test"}\n'`,
  ], 'Test arm builds the executable and runs the full suite without intervening argument changes');
}

function launcherLintContract(source) {
  // Keep collection and export together: an inventory alone cannot prove every file reaches lint.
  assert.deepEqual(launcherArm(source, 'lint'), [
    '[[ $# -eq 0 ]] || fail "lint takes no arguments."',
    'files=("$root/Package.swift")',
    "while IFS= read -r -d '' file; do",
    'files+=("$file")',
    'done < <(find "$root/Sources" "$root/Tests" -type d -name .build -prune -o -type f -name \'*.swift\' -print0)',
    'export SCRIPT_INPUT_FILE_COUNT="${#files[@]}"',
    'for index in "${!files[@]}"; do',
    'export "SCRIPT_INPUT_FILE_$index=${files[$index]}"',
    'done',
    'swiftlint lint --config "$root/../../.swiftlint.yml" --no-cache --use-script-input-files >&2 ||',
    'fail "Native tool lint failed."',
    String.raw`printf '{"ok":true,"command":"lint"}\n'`,
  ], 'Lint initializes, appends, enumerates and exports every input before the canonical lint command');
}

for (const name of readdirSync(new URL('.github/workflows/', root)).filter((name) => /\.ya?ml$/.test(name))) {
  test(`${name}: parses as strict YAML (run blocks remain data)`, () => parse(read(`.github/workflows/${name}`)));
}

test('reject malformed YAML', () => assert.throws(() => parse('on: [pocket\n')));
test('reject duplicate YAML keys, including nested branches', () => {
  assert.throws(() => parse('on: {}\non: {}\n'));
  assert.throws(() => parse('on:\n  push:\n    branches: [pocket]\n    branches: [dev]\n'));
});
test('YAML 1.2 preserves on as a string key', () => assert.deepEqual(parse('on: {push: {branches: [pocket]}}'), {
  on: { push: { branches: ['pocket'] } },
}));

test('product app matrix, build/test and check identities', () => appContract(workflow('cicd')));
test('product SwiftLint remains non-strict and uses the existing config', () => lintContract(workflow('swiftlint')));
test('CodeQL retains all scans and separately extracts app and helper after init', () => codeqlContract(workflow('codeql')));
test('hosted helper uses only canonical permission-free checks', () => hostedContract(workflow('notch_control'), 'helper'));
test('hosted contracts also execute the existing PR policy suite without path filtering', () => hostedContract(workflow('ci_contract_tests'), 'contracts'));

const actionFixtures = [
  ['cicd', appContract, 'build', ['Checkout']],
  ['cicd', appContract, 'build', ['Build']],
  ['cicd', appContract, 'build', ['Test']],
  ['swiftlint', lintContract, 'swiftlint', ['Checkout']],
  ['codeql', codeqlContract, 'analyze', ['Checkout repository']],
  ['codeql', codeqlContract, 'analyze', ['Initialize CodeQL', 'Perform CodeQL Analysis']],
  ['notch_control', (c) => hostedContract(c, 'helper'), 'validate', ['Checkout']],
  ['ci_contract_tests', (c) => hostedContract(c, 'contracts'), 'test', ['Checkout']],
];
const replacementCommit = (uses) => uses.endsWith(`@${'1'.repeat(40)}`) ? '2'.repeat(40) : '1'.repeat(40);

for (const [file, check, jobId, names] of actionFixtures) {
  test(`accept immutable action update: ${file} ${names.join(' + ')}`, () => {
    const config = workflow(file);
    const job = config.jobs[jobId];
    const commit = replacementCommit(step(job, names[0]).uses);
    for (const name of names) {
      const action = step(job, name);
      action.uses = `${action.uses.split('@')[0]}@${commit}`;
    }
    assert.doesNotThrow(() => check(config));
  });
  for (const name of names) {
    for (const mutation of ['wrong identity', 'floating tag']) {
      test(`reject action ${mutation}: ${file} ${name}`, () => {
        const config = workflow(file);
        const action = step(config.jobs[jobId], name);
        const [identity, commit] = action.uses.split('@');
        action.uses = mutation === 'wrong identity' ? `unexpected/action@${commit}` : `${identity}@v4`;
        assert.throws(() => check(config), assert.AssertionError);
      });
    }
  }
}

test('Dependabot retains all three weekly ecosystems and directories, targeting pocket', () => {
  assert.deepEqual(parse(read('.github/dependabot.yml')), { version: 2, updates: [
    ['github-actions', '/'], ['pip', '/Configuration/dmg'], ['swift', '/'],
  ].map(([ecosystem, directory]) => ({
    'package-ecosystem': ecosystem, directory, schedule: { interval: 'weekly' }, 'target-branch': 'pocket',
  })) });
});

test('PR policy identities, events and permissions remain unchanged', () => {
  for (const [file, jobId, name, permissions] of [
    ['base_ref_check', 'validate', 'Fork PR target check', { 'pull-requests': 'read' }],
    ['base_ref_check_comment', 'comment', 'Sync PR target guidance comment', { issues: 'write', 'pull-requests': 'write' }],
  ]) {
    const config = workflow(file);
    assert.deepEqual(config.on, { pull_request_target: {
      types: ['opened', 'reopened', 'synchronize', 'edited', 'ready_for_review'],
    } });
    assert.deepEqual(config.permissions, {});
    assert.equal(config.jobs[jobId].name, name);
    assert.deepEqual(config.jobs[jobId].permissions, permissions);
  }
  const oldTests = workflow('pr_target_policy_tests');
  assert.equal(oldTests.jobs.test.name, 'Test PR target policy');
  const paths = [
    '.github/workflows/base_ref_check.yml', '.github/workflows/base_ref_check_comment.yml',
    '.github/workflows/pr_target_policy_tests.yml', '.github/scripts/pr-target-policy.test.cjs',
  ];
  assert.deepEqual(oldTests.on, {
    pull_request: { paths }, push: { branches: ['pocket'], paths },
  });
});

test('canonical helper launcher includes all 41 tests and exactly nine Swift lint inputs', () => {
  const packageRoot = new URL('scripts/notch-control/', root);
  const swiftFiles = ['Package.swift', ...['Sources', 'Tests'].flatMap((folder) =>
    readdirSync(new URL(`${folder}/`, packageRoot), { recursive: true })
      .filter((path) => path.endsWith('.swift')).map((path) => `${folder}/${path}`))].sort();
  assert.deepEqual(swiftFiles, [
    'Package.swift', 'Sources/ControlCore/ControlCore.swift', 'Sources/ControlCore/SecureOutput.swift',
    'Sources/NotchControl/Accessibility.swift', 'Sources/NotchControl/AppTarget.swift',
    'Sources/NotchControl/Capture.swift', 'Sources/NotchControl/NotchControl.swift',
    'Tests/ControlCoreTests/ControlCoreTests.swift',
    'Tests/ControlCoreTests/NotchActionTests.swift',
  ]);
  const launcher = read('scripts/notch-control/control.sh');
  launcherTestContract(launcher);
  launcherLintContract(launcher);
  const tests = swiftFiles.filter((path) => path.startsWith('Tests/'))
    .map((path) => read(`scripts/notch-control/${path}`)).join('\n');
  assert.equal([...tests.matchAll(/^\s+func test\w+\(/gm)].length, 41);
});

test('reject actual-source mutation: Swift test filter after redirection', () => {
  const launcher = read('scripts/notch-control/control.sh');
  launcherTestContract(launcher);
  const filtered = launcher.replace(swiftTestInvocation,
    'xcrun swift test "${common[@]}" >&2 --filter ControlCoreTests.testValidCommands || fail "Native tool tests failed."');
  assert.notEqual(filtered, launcher, 'Fixture must mutate the effective Swift test invocation');
  assert.throws(() => launcherTestContract(filtered), assert.AssertionError);
});

for (const [name, before, after] of [
  ['filter in shared definition', commonDefinition[0], `${commonDefinition[0]} --filter ControlCoreTests.testValidCommands`],
  ['shared append before dispatch', 'case "$mode" in', 'common+=(--filter ControlCoreTests.testValidCommands)\ncase "$mode" in'],
  ['indirect filter after preliminary build/export', testExecutableExport,
    `${testExecutableExport}\n        common+=(--filter ControlCoreTests.testValidCommands)`],
  ['test-arm argument reassignment', testExecutableExport,
    `${testExecutableExport}\n        common=(--package-path "$root" --filter ControlCoreTests.testValidCommands)`],
]) {
  test(`reject actual-source mutation: ${name}`, () => {
    const launcher = read('scripts/notch-control/control.sh');
    const mutated = launcher.replace(before, after);
    assert.notEqual(mutated, launcher, 'Fixture must change the shared Swift test arguments');
    assert.throws(() => launcherTestContract(mutated), assert.AssertionError);
  });
}

for (const [name, before, after] of [
  ['lost lint initialization', 'files=("$root/Package.swift")', 'files=()'],
  ['lint collector reset instead of append', 'files+=("$file")', 'files=("$file")'],
  ['lint inputs reassigned before export', 'export SCRIPT_INPUT_FILE_COUNT="${#files[@]}"',
    'files=("$root/Package.swift")\n        export SCRIPT_INPUT_FILE_COUNT="${#files[@]}"'],
  ['lost lint enumeration', 'for index in "${!files[@]}"; do', 'for index in 0; do'],
  ['lost lint count export', 'export SCRIPT_INPUT_FILE_COUNT="${#files[@]}"', ''],
  ['lost lint file export', 'export "SCRIPT_INPUT_FILE_$index=${files[$index]}"', ''],
]) {
  test(`reject actual-source mutation: ${name}`, () => {
    const launcher = read('scripts/notch-control/control.sh');
    const mutated = launcher.replace(before, after);
    assert.notEqual(mutated, launcher, 'Fixture must change the lint input collection/export');
    assert.throws(() => launcherLintContract(mutated), assert.AssertionError);
  });
}

test('packaging uses project/scheme notchPocket, but notch-pocket.app and .dmg', () => {
  packagingContract(workflow('build_reusable'), workflow('release'));
  const project = read('notchPocket.xcodeproj/project.pbxproj');
  assert.equal([...project.matchAll(/PRODUCT_NAME = "notch-pocket";/g)].length, 2);
  assert.match(project, /path = notch-pocket\.app;/);
  assert.ok(project.includes('TEST_HOST = "$(BUILT_PRODUCTS_DIR)/notch-pocket.app/'));
});

test('manual signing, dev-to-main release, translations and issue-form writes remain deferred', () => {
  const manual = workflow('manual_build');
  assert.deepEqual(Object.keys(manual.on), ['workflow_dispatch']);
  assert.equal(manual.on.workflow_dispatch.inputs.head_ref.default, 'main');
  assert.equal(manual.on.workflow_dispatch.inputs.xcode_version.default, '16.4');
  assert.ok(manual.jobs.build.with.head_ref.endsWith("|| 'main' }}"));
  const reusable = workflow('build_reusable');
  assert.deepEqual(Object.keys(reusable.on), ['workflow_call']);
  assert.equal(reusable.on.workflow_call.inputs.xcode_version.default, '16.4');
  assert.equal(reusable.jobs.build.env.EXPORT_METHOD, 'development');
  const release = workflow('release');
  assert.deepEqual(release.on, { issue_comment: { types: ['created'] } });
  assert.equal(release.env.XCODE_VERSION, '16.4');
  assert.ok(release.jobs.check_release.steps[0].run.includes('"$HEAD_REF" == "dev" && "$BASE_REF" == "main"'));
  const crowdin = workflow('crowdin');
  assert.deepEqual(crowdin.on, { push: { branches: ['dev'] }, workflow_dispatch: null });
  assert.equal(step(crowdin.jobs.crowdin, 'Crowdin action').with.pull_request_base_branch_name, 'dev');
  const dropdown = workflow('update-version-dropdown');
  assert.deepEqual(dropdown.on, {
    push: { tags: ['*'] }, workflow_dispatch: {}, release: { types: ['published'] },
  });
  assert.equal(dropdown.jobs['update-dropdown'].steps[0].with.ref, '${{ github.event.repository.default_branch }}');
});

const mutations = [
  ['legacy app push', 'cicd', appContract, (c) => { c.on.push.branches = ['dev']; }],
  ['legacy PR base', 'swiftlint', lintContract, (c) => { c.on.pull_request.branches = ['main']; }],
  ['wildcard push', 'cicd', appContract, (c) => { c.on.push.branches = ['*']; }],
  ['lost app matrix leg', 'cicd', appContract, (c) => { c.jobs.build.strategy.matrix.include.pop(); }],
  ['skipped app tests', 'cicd', appContract, (c) => { step(c.jobs.build, 'Test').if = 'false'; }],
  ['changed CodeQL schedule', 'codeql', codeqlContract, (c) => { c.on.schedule = []; }],
  ['lost scan language', 'codeql', codeqlContract, (c) => { c.jobs.analyze.strategy.matrix.include.shift(); }],
  ['lost scan permission', 'codeql', codeqlContract, (c) => { delete c.jobs.analyze.permissions['security-events']; }],
  ['lost Swift-only dependency resolution', 'codeql', codeqlContract, (c) => {
    delete step(c.jobs.analyze, 'Resolve Swift package dependencies').if;
  }],
  ['mismatched CodeQL versions', 'codeql', codeqlContract, (c) => {
    step(c.jobs.analyze, 'Perform CodeQL Analysis').uses =
      `${codeql}/analyze@${replacementCommit(step(c.jobs.analyze, 'Initialize CodeQL').uses)}`;
  }],
  ['wrong CodeQL subpath', 'codeql', codeqlContract, (c) => {
    step(c.jobs.analyze, 'Perform CodeQL Analysis').uses = step(c.jobs.analyze, 'Initialize CodeQL').uses;
  }],
  ['helper replacing app extraction', 'codeql', codeqlContract, (c) => { step(c.jobs.analyze, 'Build Notch Pocket').run = `${helper} build`; }],
  ['helper before CodeQL init', 'codeql', codeqlContract, (c) => {
    const steps = c.jobs.analyze.steps;
    steps.splice(1, 0, steps.splice(4, 1)[0]);
  }],
  ['helper path filter', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { c.on.pull_request.paths = ['scripts/**']; }],
  ['helper tests filtered', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { step(c.jobs.validate, 'Test helper').run += ' --filter one'; }],
  ['app lint instead of helper lint', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { step(c.jobs.validate, 'Lint helper').run = 'scripts/lint.sh'; }],
  ['helper credentials persisted', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { c.jobs.validate.steps[0].with['persist-credentials'] = true; }],
  ['helper write permissions', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { c.permissions.contents = 'write'; }],
  ['helper runtime step', 'notch_control', (c) => hostedContract(c, 'helper'), (c) => { c.jobs.validate.steps.push({ run: `${helper} run inspect` }); }],
  ['missing policy regression run', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    c.jobs.test.steps = c.jobs.test.steps.filter(({ name }) => name !== 'Test PR target policy');
  }],
  ['missing packaging regression run', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    c.jobs.test.steps = c.jobs.test.steps.filter(({ name }) => name !== 'Test local packaging policy');
  }],
  ['filtered packaging tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local packaging policy').run += ' -k test_success';
  }],
  ['skipped packaging tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local packaging policy').if = 'false';
  }],
  ['ignored packaging failures', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local packaging policy')['continue-on-error'] = true;
  }],
  ['masked packaging exit status', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local packaging policy').run += ' || true';
  }],
  ['packaging workflow path filter', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    c.on.pull_request.paths = ['scripts/package.py'];
  }],
];
for (const [name, file, check, mutate] of mutations) {
  test(`reject actual-config mutation: ${name}`, () => {
    const config = workflow(file);
    mutate(config);
    assert.throws(() => check(config), assert.AssertionError);
  });
}
test('reject actual-config mutation: project-derived app artifact', () => {
  const reusable = workflow('build_reusable');
  step(reusable.jobs.build, 'Upload .app').with.path = 'Release/${{ env.PROJECT_NAME }}.app';
  assert.throws(() => packagingContract(reusable, workflow('release')), assert.AssertionError);
});
