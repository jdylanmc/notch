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
const wrapperTests = "python3 -B -m unittest discover -s scripts/tests -p 'test_build_wrappers.py'";

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
    { name: 'Test build wrapper contracts', run: wrapperTests },
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
  assert.equal(job['runs-on'], "${{ (matrix.language == 'swift' && 'macos-26') || 'ubuntu-latest' }}");
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
    'Checkout repository', 'Select stable Swift toolchain', 'Resolve Swift package dependencies', 'Initialize CodeQL',
    'Build Notch Pocket', 'Build notch-control', 'Perform CodeQL Analysis',
  ]);
  assert.deepEqual(step(job, 'Checkout repository'), {
    name: 'Checkout repository', uses: pinnedAction(job, 'Checkout repository', checkout), with: { 'persist-credentials': false },
  });
  assert.deepEqual(step(job, 'Select stable Swift toolchain'), {
    name: 'Select stable Swift toolchain', if: "matrix.language == 'swift'",
    run: 'developer=/Applications/Xcode_26.6.app/Contents/Developer\n'
      + 'test -x "$developer/usr/bin/xcodebuild"\n'
      + 'echo "DEVELOPER_DIR=$developer" >> "$GITHUB_ENV"\n',
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
          { name: 'Test local distribution signing policy', run: "python3 -B -m unittest discover -s scripts/tests -p 'test_distribution.py'" },
          { name: 'Test notarization preparation policy', run: "python3 -B -m unittest discover -s scripts/tests -p 'test_notarize.py'" },
          { name: 'Test hosted release boundaries', run: "python3 -B -m unittest discover -s scripts/tests -p 'test_pocket_release.py'" },
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

test('canonical helper launcher includes all 55 tests and exactly nine Swift lint inputs', () => {
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
  assert.equal([...tests.matchAll(/^\s+func test\w+\(/gm)].length, 55);
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
  assert.deepEqual(dropdown.on, { workflow_dispatch: {} });
  assert.equal(dropdown.jobs['update-dropdown'].steps[0].with.ref, '${{ github.event.repository.default_branch }}');
});

const mutations = [
  ['legacy app push', 'cicd', appContract, (c) => { c.on.push.branches = ['dev']; }],
  ['legacy PR base', 'swiftlint', lintContract, (c) => { c.on.pull_request.branches = ['main']; }],
  ['wildcard push', 'cicd', appContract, (c) => { c.on.push.branches = ['*']; }],
  ['lost app matrix leg', 'cicd', appContract, (c) => { c.jobs.build.strategy.matrix.include.pop(); }],
  ['skipped app tests', 'cicd', appContract, (c) => { step(c.jobs.build, 'Test').if = 'false'; }],
  ['missing build wrapper contracts', 'cicd', appContract, (c) => {
    c.jobs.build.steps = c.jobs.build.steps.filter(({ name }) => name !== 'Test build wrapper contracts');
  }],
  ['skipped build wrapper contracts', 'cicd', appContract, (c) => {
    step(c.jobs.build, 'Test build wrapper contracts').if = 'false';
  }],
  ['ignored build wrapper failures', 'cicd', appContract, (c) => {
    step(c.jobs.build, 'Test build wrapper contracts')['continue-on-error'] = true;
  }],
  ['masked build wrapper exit status', 'cicd', appContract, (c) => {
    step(c.jobs.build, 'Test build wrapper contracts').run += ' || true';
  }],
  ['changed CodeQL schedule', 'codeql', codeqlContract, (c) => { c.on.schedule = []; }],
  ['preview Swift scan runner', 'codeql', codeqlContract, (c) => {
    c.jobs.analyze['runs-on'] = "${{ (matrix.language == 'swift' && 'xcode-27') || 'ubuntu-latest' }}";
  }],
  ['missing stable Swift toolchain', 'codeql', codeqlContract, (c) => {
    c.jobs.analyze.steps = c.jobs.analyze.steps.filter(({ name }) => name !== 'Select stable Swift toolchain');
  }],
  ['unselected stable Swift toolchain', 'codeql', codeqlContract, (c) => {
    step(c.jobs.analyze, 'Select stable Swift toolchain').run = 'xcodebuild -version';
  }],
  ['ignored stable toolchain failure', 'codeql', codeqlContract, (c) => {
    step(c.jobs.analyze, 'Select stable Swift toolchain')['continue-on-error'] = true;
  }],
  ['stable toolchain after CodeQL init', 'codeql', codeqlContract, (c) => {
    const steps = c.jobs.analyze.steps;
    const selection = steps.splice(steps.findIndex(({ name }) => name === 'Select stable Swift toolchain'), 1)[0];
    steps.splice(steps.findIndex(({ name }) => name === 'Initialize CodeQL') + 1, 0, selection);
  }],
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
    const build = steps.splice(steps.findIndex(({ name }) => name === 'Build notch-control'), 1)[0];
    steps.splice(1, 0, build);
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
  ['missing distribution signing run', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    c.jobs.test.steps = c.jobs.test.steps.filter(({ name }) => name !== 'Test local distribution signing policy');
  }],
  ['filtered distribution signing tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local distribution signing policy').run += ' -k test_success';
  }],
  ['skipped distribution signing tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local distribution signing policy').if = 'false';
  }],
  ['ignored distribution signing failures', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local distribution signing policy')['continue-on-error'] = true;
  }],
  ['masked distribution signing exit status', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test local distribution signing policy').run += ' || true';
  }],
  ['missing notarization tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    c.jobs.test.steps = c.jobs.test.steps.filter(({ name }) => name !== 'Test notarization preparation policy');
  }],
  ['filtered notarization tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test notarization preparation policy').run += ' -k success';
  }],
  ['skipped notarization tests', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test notarization preparation policy').if = 'false';
  }],
  ['ignored notarization failures', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test notarization preparation policy')['continue-on-error'] = true;
  }],
  ['masked notarization exit status', 'ci_contract_tests', (c) => hostedContract(c, 'contracts'), (c) => {
    step(c.jobs.test, 'Test notarization preparation policy').run += ' || true';
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

function pocketReleaseContract(config) {
  const sha = '${{ needs.gate.outputs.sha }}';
  const version = '${{ needs.gate.outputs.version }}';
  const sourceEnv = { SOURCE_SHA: sha, VERSION: version };
  const githubEnv = { GITHUB_TOKEN: '${{ github.token }}' };
  const tapEnv = { HOMEBREW_TAP_TOKEN: '${{ secrets.HOMEBREW_TAP_TOKEN }}' };
  const appleEnv = Object.fromEntries([
    'APPLE_CERTIFICATE_P12', 'APPLE_CERTIFICATE_PASSWORD', 'APPLE_NOTARY_KEY_P8',
    'APPLE_NOTARY_KEY_ID', 'APPLE_NOTARY_ISSUER_ID', 'APPLE_TEAM_ID', 'APPLE_SIGNING_IDENTITY',
  ].map((name) => [name, `\${{ secrets.${name} }}`]));
  const action = (job, name, repository, minutes, options) => ({
    name, uses: pinnedAction(config.jobs[job], name, repository), 'timeout-minutes': minutes, with: options,
  });
  const checkoutSource = (job, minutes) => action(job, 'Checkout gated source', checkout, minutes,
    { ref: sha, 'persist-credentials': false });
  const run = (name, minutes, command, env) => ({
    name, 'timeout-minutes': minutes, ...(env ? { env } : {}), run: command,
  });
  const download = (job) => action(job, 'Download final public assets', 'actions/download-artifact', 3,
    { name: 'notch-pocket-release', path: '.build/pocket-release-assets' });
  const release = 'python3 -B .github/scripts/pocket_release.py';
  const sign = 'python3 -B .github/scripts/pocket_sign.py';
  assert.deepEqual(config, {
    name: 'Notch Pocket notarized release',
    on: {
      push: { tags: ['notch-pocket-v*'] },
      workflow_dispatch: { inputs: { tag: {
        description: 'Existing product tag, exactly matching distribution.VERSION', required: true, type: 'string',
      } } },
    },
    permissions: {},
    concurrency: { group: 'notch-pocket-release', 'cancel-in-progress': false },
    defaults: { run: { shell: 'bash --noprofile --norc -euo pipefail {0}' } },
    jobs: {
      gate: {
        'runs-on': 'ubuntu-latest', 'timeout-minutes': 10, permissions: { contents: 'read', actions: 'read' },
        outputs: { sha: '${{ steps.source.outputs.sha }}', version: '${{ steps.source.outputs.version }}' },
        steps: [
          action('gate', 'Checkout trusted gate', checkout, 3,
            { ref: 'pocket', 'fetch-depth': 0, 'persist-credentials': false }),
          { ...run('Validate tag and nine exact-commit checks', 6, `${release} gate`,
            { ...githubEnv, RELEASE_TAG: "${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name }}" }),
          id: 'source' },
        ],
      },
      'tap-ready': {
        needs: 'gate', 'runs-on': 'ubuntu-latest', environment: 'notch-pocket-tap',
        'timeout-minutes': 5, permissions: { contents: 'read' },
        steps: [checkoutSource('tap-ready', 2), run('Check scoped tap configuration', 2, `${release} tap-ready`, tapEnv)],
      },
      sign: {
        needs: ['gate', 'tap-ready'], 'runs-on': 'macos-26', environment: 'notch-pocket-release',
        'timeout-minutes': 150, permissions: { contents: 'read' },
        env: { DEVELOPER_DIR: '/Applications/Xcode_26.6.app/Contents/Developer', ...sourceEnv },
        steps: [
          checkoutSource('sign', 3),
          run('Check Apple configuration', 1, `${sign} config`, appleEnv),
          run('Verify hosted tools', 3, `${sign} tools`),
          run('Prepare isolated pinned DMG dependencies', 10, [
            'umask 077', 'mkdir -p .build', 'test ! -e .build/pocket-release-venv',
            'python3 -m venv .build/pocket-release-venv',
            "if ! .build/pocket-release-venv/bin/python3 -c 'import dmgbuild' >/dev/null 2>&1; then",
            '  .build/pocket-release-venv/bin/python3 -m pip install --disable-pip-version-check --require-hashes --only-binary=:all: -r Configuration/dmg/requirements.txt',
            'fi', ".build/pocket-release-venv/bin/python3 -c 'import dmgbuild'",
            'printf \'%s\\n\' "$GITHUB_WORKSPACE/.build/pocket-release-venv/bin" >> "$GITHUB_PATH"', '',
          ].join('\n')),
          run('Build exact Release app and notarize final DMG', 120, `${sign} sign`, appleEnv),
          { ...run('Always restore keychain search list and remove credentials', 5, `${sign} cleanup`), if: 'always()' },
          action('sign', 'Upload only final public assets', 'actions/upload-artifact', 5, {
            name: 'notch-pocket-release',
            path: `.build/pocket-release-assets/notch-pocket-${version}.dmg\n.build/pocket-release-assets/manifest.json\n`,
            'include-hidden-files': true,
            'if-no-files-found': 'error', 'retention-days': 7, 'compression-level': 0,
          }),
        ],
      },
      publish: {
        needs: ['gate', 'sign'], 'runs-on': 'ubuntu-latest', 'timeout-minutes': 20,
        permissions: { contents: 'write', actions: 'read' },
        steps: [checkoutSource('publish', 2), download('publish'),
          run('Verify bytes and draft then publish latest', 14, `${release} publish`, { ...githubEnv, ...sourceEnv })],
      },
      tap: {
        needs: ['gate', 'publish'], 'runs-on': 'ubuntu-latest', environment: 'notch-pocket-tap',
        'timeout-minutes': 15, permissions: { contents: 'read' },
        steps: [checkoutSource('tap', 2), download('tap'),
          run('Verify published bytes and open tap PR', 9, `${release} tap`, { ...githubEnv, ...tapEnv, ...sourceEnv })],
      },
    },
  });
}

test('product release isolates gated SHA, hosted Apple secrets, publication and PR-only tap credentials', () => {
  pocketReleaseContract(workflow('pocket-native-release'));
});

for (const [name, mutate] of [
  ['inherited tag prefix', (c) => { c.on.push.tags = ['v*']; }],
  ['branch trigger', (c) => { c.on.push.branches = ['pocket']; }],
  ['manual tag default', (c) => { c.on.workflow_dispatch.inputs.tag.default = 'v2.7'; }],
  ['untrusted gate checkout', (c) => { c.jobs.gate.steps[0].with.ref = '${{ inputs.tag }}'; }],
  ['tag instead of pinned source', (c) => { c.jobs.sign.steps[0].with.ref = '${{ inputs.tag }}'; }],
  ['persisted checkout credentials', (c) => { c.jobs.sign.steps[0].with['persist-credentials'] = true; }],
  ['floating action', (c) => { c.jobs.sign.steps[0].uses = 'actions/checkout@v7'; }],
  ['untrusted action', (c) => { c.jobs.sign.steps[0].uses = `other/checkout@${'a'.repeat(40)}`; }],
  ['tag interpolation into shell', (c) => { c.jobs.gate.steps[1].run += ' "${{ inputs.tag }}"'; }],
  ['secret workflow output', (c) => { c.jobs.gate.outputs.key = '${{ secrets.APPLE_NOTARY_KEY_P8 }}'; }],
  ['signing job write token', (c) => { c.jobs.sign.permissions.contents = 'write'; }],
  ['Apple secrets in publisher', (c) => { c.jobs.publish.env = { APPLE_TEAM_ID: '${{ secrets.APPLE_TEAM_ID }}' }; }],
  ['tap token fallback', (c) => {
    step(c.jobs.tap, 'Verify published bytes and open tap PR').env.HOMEBREW_TAP_TOKEN = '${{ secrets.HOMEBREW_TAP_TOKEN || github.token }}';
  }],
  ['legacy reusable builder', (c) => { c.jobs.sign.uses = './.github/workflows/build_reusable.yml'; }],
  ['wrong macOS runner', (c) => { c.jobs.sign['runs-on'] = 'macos-latest'; }],
  ['implicit Xcode', (c) => { delete c.jobs.sign.env.DEVELOPER_DIR; }],
  ['lost job timeout', (c) => { delete c.jobs.sign['timeout-minutes']; }],
  ['lost step timeout', (c) => { delete c.jobs.sign.steps[4]['timeout-minutes']; }],
  ['skipped native signing', (c) => { c.jobs.sign.steps[4].if = 'false'; }],
  ['native failure masked', (c) => { c.jobs.sign.steps[4].run += ' || true'; }],
  ['cleanup failure ignored', (c) => { c.jobs.sign.steps[5]['continue-on-error'] = true; }],
  ['cleanup not always', (c) => { delete c.jobs.sign.steps[5].if; }],
  ['upload despite failure', (c) => { c.jobs.sign.steps[6].if = 'always()'; }],
  ['missing hidden-file opt-in', (c) => { delete c.jobs.sign.steps[6].with['include-hidden-files']; }],
  ['disabled hidden-file opt-in', (c) => { c.jobs.sign.steps[6].with['include-hidden-files'] = false; }],
  ['upload private residue', (c) => { c.jobs.sign.steps[6].with.path = '.build'; }],
  ['upload public directory glob', (c) => { c.jobs.sign.steps[6].with.path = '.build/pocket-release-assets/**'; }],
  ['upload additional private path', (c) => { c.jobs.sign.steps[6].with.path += '.build/pocket-release-notarized/evidence.json\n'; }],
  ['release before successful signing', (c) => { c.jobs.publish.needs = ['gate']; }],
  ['tap before publication', (c) => { c.jobs.tap.needs = ['gate', 'sign']; }],
  ['dependency hash enforcement lost', (c) => { c.jobs.sign.steps[3].run = c.jobs.sign.steps[3].run.replace('--require-hashes ', ''); }],
  ['dependency credentials exposed', (c) => { c.jobs.sign.steps[3].env = c.jobs.sign.steps[1].env; }],
  ['overlapping signing cancellation', (c) => { c.concurrency['cancel-in-progress'] = true; }],
]) {
  test(`reject release mutation: ${name}`, () => {
    const config = workflow('pocket-native-release');
    mutate(config);
    assert.throws(() => pocketReleaseContract(config), assert.AssertionError);
  });
}

for (const [name, mutate] of [
  ['missing', (s) => s.pop()],
  ['filtered', (s) => { s.at(-1).run += ' -k success'; }],
  ['skipped', (s) => { s.at(-1).if = 'false'; }],
  ['ignored', (s) => { s.at(-1)['continue-on-error'] = true; }],
  ['masked', (s) => { s.at(-1).run += ' || true'; }],
]) {
  test(`reject release test mutation: ${name}`, () => {
    const config = workflow('ci_contract_tests');
    mutate(config.jobs.test.steps);
    assert.throws(() => hostedContract(config, 'contracts'), assert.AssertionError);
  });
}

test('product release cannot trigger issue-form commits; dropdown script remains manual', () => {
  const config = workflow('update-version-dropdown');
  assert.deepEqual(config.on, { workflow_dispatch: {} });
  assert.deepEqual(config.permissions, { contents: 'write' });
  assert.ok(step(config.jobs['update-dropdown'], 'Commit changes').run.includes('git push'));
});
