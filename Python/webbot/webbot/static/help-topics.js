/** Help topic registry for the Webbot dashboard (content only). */

function helpTable(headers, rows) {
  const head = headers.map((h) => `<th scope="col">${h}</th>`).join("");
  const body = rows
    .map((cells) => {
      const [first, ...rest] = cells;
      const rowHead = `<th scope="row">${first}</th>`;
      const cols = rest.map((c) => `<td>${c}</td>`).join("");
      return `<tr>${rowHead}${cols}</tr>`;
    })
    .join("");
  return `<table class="help-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

const HELP_TOPICS = {
  overview: {
    title: "Webbot overview",
    body: [
      "<p>Webbot runs human-like browser automation: curved mouse moves, variable delays, and a persistent profile. The dashboard always runs flows with <strong>Playwright</strong> (JSON and Python). <strong>Nodriver</strong>, when installed, is only for the CLI <code>open</code> command with <code>--driver nodriver</code> — it does not apply to runs started from this UI.</p>",
      "<p>Use the top tabs to switch between <strong>Workspace</strong> (editor and log) and <strong>Flow groups</strong> (sidebar sections). Pick a flow in the sidebar, edit it on the right, and press <strong>Start</strong> or use <strong>Run group</strong> on a section. Flows can be JSON (step builder) or Python (editable source panel). Use <strong>run_scenario</strong> steps in JSON flows to compose subflows of either kind.</p>",
      "<p>Scenarios live under <code>%APPDATA%/webbot/scenarios/</code> on Windows (or <code>~/.config/webbot/scenarios/</code> elsewhere): <code>.json</code> for JSON flows and <code>.py</code> for Python flows (only one extension per flow name). Group membership is stored in <code>%APPDATA%/webbot/groups.json</code> (or <code>~/.config/webbot/groups.json</code> elsewhere), beside the scenarios folder.</p>",
    ],
  },
  "help.home": {
    title: "Workspace",
    body: [
      "<p>Three columns: <strong>Flows</strong> (tall list), the <strong>editor</strong> in the center, and <strong>Run</strong> on the right. The log sits below.</p>",
      helpTable(
        ["Area", "What it does"],
        [
          ["Flows", "Grouped sections and ungrouped; pick one to edit. Run status (colored dot and label) appears above the flow list. Use the filter box to narrow by flow name or description. <strong>New flow</strong> creates a draft from <strong>Flow type</strong>. <strong>Delete</strong> (next to <strong>Save</strong> and <strong>Test run</strong>) removes the selected flow from disk <em>and</em> drops it from all groups automatically; drafts are discarded instead. Organize sections under the <strong>Flow groups</strong> tab."],
          ["Editor", "JSON: name, URL, options, steps (drag to reorder). Python: source editor; flow name is read-only once saved. <strong>Ctrl/Cmd+S</strong> saves the current flow; <strong>Ctrl/Cmd+Enter</strong> saves and starts a run (same as Test run)."],
          ["Run", "Loops, pauses between loops and group runs, headless, Playwright <strong>Browser channel</strong> and <strong>Slow motion (ms)</strong> (CLI <code>--channel</code> / <code>--slow-mo</code>), Start/Stop. Run options are remembered in this browser (local storage). Live logs use the websocket indicator next to version in the header (reconnects with exponential backoff when the connection drops)."],
          ["Save / Test run", "Save JSON or Python to disk, or save and run immediately. Use <strong>Duplicate</strong> / <strong>Export</strong> / <strong>Import</strong> in the button row to copy flows or move them as files."],
          ["Log", "Live output from the runner."],
        ]
      ),
      "<p>Use the sidebar in this dialog for step types, locators, and detailed field help.</p>",
    ],
  },
  "help.run": {
    title: "Run tab",
    body: [
      "<p>Pick a flow, preview its steps, set options, and start a run. The log and step list update live while the browser runs.</p>",
      helpTable(
        ["Control", "What it does"],
        [
          ["Scenarios", "Select a saved flow from the sidebar (ungrouped or inside a section)."],
          ["Filter flows", "Search box narrows sidebar rows by flow name or description without changing what is saved."],
          ["Loops", "How many full passes through the flow."],
          ["Pause between loops", "Wait time after each full pass (except the last)."],
          ["Pause between flows in group", "Seconds to wait between flows when using Run group."],
          ["Browser channel", "Playwright channel: Chrome, Chromium, or Edge — same as CLI <code>--channel</code>."],
          ["Slow motion (ms)", "Optional delay injected between Playwright actions for debugging (<code>--slow-mo</code>)."],
          ["Headless", "Hide the browser window (faster; harder to debug)."],
          ["Live log indicator", "Header shows websocket status for streamed log/status. If the connection drops, the UI reconnects with increasing delay (capped) and also retries when you return to this tab."],
          ["Log panel", "<strong>Copy</strong> / <strong>Clear</strong> above the transcript; oldest lines trim after about 4000 lines to keep the page responsive."],
          ["Flow preview", "Step list with live green/red status during a run."],
        ]
      ),
      "<p>Use the sidebar in this dialog for details on each control.</p>",
    ],
  },
  "help.flows": {
    title: "Flows tab",
    body: [
      "<p>Create and edit flows: JSON in the step builder, or Python in the source editor. Set <strong>Flow type</strong> in the workspace form, then <strong>New flow</strong>; while editing an unsaved draft you can switch type there too (confirmed).</p>",
      helpTable(
        ["Area", "What it does"],
        [
          ["Flow list", "Grouped sections and ungrouped flows; filter by typing in the Workspace sidebar. Edit membership under the Flow groups tab."],
          ["Name / description / start URL", "Metadata; start URL is used when there is no <code>open_url</code> step."],
          ["Scenario options", "Optional random delay between every step."],
          ["Steps", "Drag by the grip to reorder. Types: open_url (navigate), goto (jump forward in this list via labels), click, fill, delay, scroll, submit_form, run_scenario, if_present, exit."],
          ["Save / Test run", "Write JSON to disk, or save and start immediately. Duplicate / Export / Import are in the same button row."],
        ]
      ),
      "<p>Use the sidebar for step types, locators, and scenario options.</p>",
    ],
  },
  "run.scenario": {
    title: "Scenarios",
    body: [
      "<p>Click a flow in the list to select it, then press <strong>Start</strong>. Use <strong>Run group</strong> on a section header to run every flow in that group in order.</p>",
      "<p>Descriptions and the <code>json</code> / <code>python</code> badges identify saved flows.</p>",
    ],
  },
  "run.loops": {
    title: "Loops",
    body: [
      "<p>How many times to run the entire scenario from the first step to the last.</p>",
      "<p>Each loop is a full pass; step progress in the run status above the flow list shows <code>loop 2/5</code> when loops &gt; 1.</p>",
    ],
  },
  "run.pause": {
    title: "Pause between loops",
    body: [
      "<p>Seconds to wait after one loop finishes and before the next starts. Ignored after the final loop.</p>",
      "<p>Useful for spacing repeated visits or cooling down between batches.</p>",
    ],
  },
  "run.headless": {
    title: "Headless",
    body: [
      "<p>Run the browser without a visible window. Faster for servers; turn off when debugging selectors or watching behavior.</p>",
    ],
  },
  "builder.name": {
    title: "Scenario name",
    body: [
      "<p>Unique identifier shown in the flow list and used as the JSON filename (<code>name.json</code>).</p>",
      "<p>Use letters, numbers, and underscores; avoid spaces.</p>",
    ],
  },
  "builder.description": {
    title: "Description",
    body: [
      "<p>Optional note shown in the scenario list. Helps you remember what a flow does.</p>",
    ],
  },
  "builder.start_url": {
    title: "Start URL",
    body: [
      "<p>If set and there is no explicit <code>open_url</code> step in the list, Webbot opens this URL as step 1 before running your steps.</p>",
      "<p>If the first step already opens a page (usually <code>open_url</code>), you can leave this empty or keep it as a default for short flows.</p>",
    ],
  },
  "builder.save": {
    title: "Save scenario",
    body: [
      "<p>Writes the current Builder form to your scenarios folder as JSON. Overwrites an existing file with the same name.</p>",
    ],
  },
  "builder.load": {
    title: "Select a flow",
    body: [
      "<p>Click a flow in the list on the left to open it in the editor.</p>",
      "<p>Use <strong>New</strong> for a blank JSON flow, or the edit icon on any row. Python flows open read-only.</p>",
    ],
  },
  "builder.test_run": {
    title: "Test run",
    body: [
      "<p>Saves the scenario and starts it immediately. Handy to verify changes without pressing Start again.</p>",
    ],
  },
  "scenario.options": {
    title: "Scenario options",
    body: [
      "<p>Settings that apply to the whole scenario, not a single step.</p>",
    ],
  },
  "scenario.random_delay": {
    title: "Random delay between steps",
    body: [
      "<p>When enabled, Webbot waits a random amount before each step after the first (including after an implicit start-URL navigation).</p>",
      "<p>Does not add a pause after the last step. Makes multi-step flows feel less robotic.</p>",
    ],
  },
  "scenario.between_steps_min": {
    title: "Between-step min",
    body: [
      "<p>Shortest pause (seconds) before the next step when random between-step delay is on.</p>",
    ],
  },
  "scenario.between_steps_max": {
    title: "Between-step max",
    body: [
      "<p>Longest pause (seconds) before the next step when random between-step delay is on.</p>",
    ],
  },
  "scenario.between_steps_distribution": {
    title: "Between-step random style",
    body: [
      "<p>How pauses are picked between min and max:</p>",
      helpTable(["Style", "Behavior"], [
        ["<code>uniform</code>", "Any value in the range is equally likely."],
        ["<code>triangular</code>", "Tends toward the middle of the range (default)."],
        ["<code>log_normal</code>", "Occasional longer pauses."],
      ]),
    ],
  },
  "builder.steps": {
    title: "Steps",
    body: [
      "<p>Ordered actions executed top to bottom. Drag by the grip to reorder; expand collapsed sections for optional settings; × removes a step.</p>",
      "<p>Add steps with <strong>Add step</strong>; change <strong>Step type</strong> to switch action kind.</p>",
    ],
  },
  "step.types": {
    title: "Step types",
    body: [
      "<p>Each step in a scenario has one action type:</p>",
      helpTable(["Type", "What it does"], [
        ["<code>open_url</code>", "Navigate to a URL in this tab (<code>page.goto</code>, domcontentloaded)."],
        ["<code>goto</code>", "Jump execution forward to a later step in the same list (targets that step’s <strong>Step label</strong>)."],
        ["<code>click</code>", "Human-like click on an element."],
        ["<code>fill</code>", "Type into one field."],
        ["<code>submit_form</code>", "Fill multiple fields and submit a form (GET or POST)."],
        ["<code>delay</code>", "Wait a random duration."],
        ["<code>scroll</code>", "Wheel scroll with optional overshoot."],
        ["<code>run_scenario</code>", "Run another saved JSON flow inline (same browser tab)."],
        ["<code>if_present</code>", "If an element is visible, run one branch of steps; otherwise the other."],
        ["<code>exit</code>", "Stop the flow successfully (remaining steps are not run)."],
      ]),
    ],
  },
  "scenario.workflow_label": {
    title: "Step label",
    body: [
      "<p>Optional text on any step (JSON field <code>workflow_label</code>). Within one step list—the main flow steps, or either branch array of <code>if_present</code>—each non-empty label must be unique.</p>",
      "<p><strong>goto</strong> steps jump forward only: their <strong>Jump to label</strong> must match another step’s <strong>Step label</strong> that appears lower in <em>that same list</em>. Webbot skips intervening verified plan rows accordingly.</p>",
    ],
  },
  "step.open_url": {
    title: "Open URL step",
    body: [
      "<p>Opens a URL in the current tab (<code>domcontentloaded</code>) with a short reading pause after load. Replaces legacy JSON <code>{\"action\":\"goto\",\"url\":\"…\"}</code> (automatically migrated to <code>open_url</code>).</p>",
    ],
  },
  "step.open_url.url": {
    title: "URL (open_url)",
    body: [
      "<p>Full address including <code>https://</code>. Example: <code>https://example.com</code>.</p>",
    ],
  },
  "step.goto": {
    title: "goto (workflow jump)",
    body: [
      "<p>Jumps execution forward inside the same step array (main flow steps, or steps inside one <code>if_present</code> branch). Targets are matched by non-empty <code>workflow_label</code> on later steps (<strong>Step label</strong> in the builder).</p>",
      "<p>Backward jumps and duplicate labels within a list raise validation errors. The run plan skips steps between the goto and the target so progress matches what actually executes.</p>",
    ],
  },
  "step.goto.target": {
    title: "Jump to label",
    body: [
      "<p>The <code>goto_label</code> field names a <strong>Step label</strong> (<code>workflow_label</code>) that must belong to a sibling step farther down the same array.</p>",
    ],
  },
  "step.click": {
    title: "Click step",
    body: [
      "<p>Moves the mouse along a curved path and clicks the target element. Configure how to find the element under <strong>Find by</strong>.</p>",
    ],
  },
  "step.fill": {
    title: "Fill step",
    body: [
      "<p>Finds an input (or contenteditable) and types the value with human-like timing. Use <strong>Value to type</strong> for the text.</p>",
    ],
  },
  "step.delay": {
    title: "Delay step",
    body: [
      "<p>Waits a random number of seconds between <strong>Min</strong> and <strong>Max</strong>. Optional long pauses simulate distraction.</p>",
    ],
  },
  "step.delay.min": {
    title: "Delay min",
    body: ["<p>Shortest random wait for this delay step, in seconds.</p>"],
  },
  "step.delay.max": {
    title: "Delay max",
    body: ["<p>Longest random wait for this delay step, in seconds.</p>"],
  },
  "step.delay.distribution": {
    title: "Delay random style",
    body: [
      "<p>How waits are sampled between min and max:</p>",
      helpTable(["Style", "Behavior"], [
        ["<code>uniform</code>", "Any value in the range is equally likely."],
        ["<code>triangular</code>", "Often shorter waits; good default."],
        ["<code>log_normal</code>", "Occasional longer waits."],
      ]),
    ],
  },
  "step.delay.long_pause": {
    title: "Long pause (delay)",
    body: [
      "<p><strong>Chance</strong> — probability (0–1) of an extra pause after the main wait.</p>",
      "<p><strong>Long pause min/max</strong> — range for that extra pause in seconds.</p>",
    ],
  },
  "step.scroll": {
    title: "Scroll step",
    body: [
      "<p>Scrolls the page using multiple wheel ticks with variable speed, optional overshoot past the target, and a pause afterward.</p>",
    ],
  },
  "step.scroll.delta_y": {
    title: "Pixels (delta Y)",
    body: [
      "<p>Total vertical scroll in pixels. Positive scrolls down; negative scrolls up.</p>",
    ],
  },
  "step.scroll.ticks": {
    title: "Wheel ticks",
    body: [
      "<p><strong>Min/max ticks</strong> — random number of small wheel steps used to cover <strong>delta Y</strong>. More ticks = smoother, slower scroll.</p>",
      "<p><strong>Delay min/max</strong> — pause between each tick in seconds.</p>",
    ],
  },
  "step.scroll.overscroll": {
    title: "Overscroll",
    body: [
      "<p>When enabled, scrolls slightly past the target then scrolls back — more human-like than stopping exactly.</p>",
      "<p><strong>Overshoot min/max (ratio)</strong> — fraction of total scroll used for overshoot (e.g. 0.1 = 10%).</p>",
    ],
  },
  "step.scroll.after": {
    title: "After scroll",
    body: [
      "<p><strong>Pause min/max</strong> — idle time after scrolling finishes.</p>",
      "<p><strong>Variable tick size</strong> — each wheel tick moves a slightly random amount.</p>",
    ],
  },
  "step.run_scenario": {
    title: "Run scenario step",
    body: [
      "<p>Loads another JSON flow by name and runs its steps inline in the same browser session.</p>",
      "<p><strong>Flow to run</strong> — must be a saved JSON scenario (cannot be the same file you are editing).</p>",
      "<p><strong>Use parent delay settings</strong> — when checked, random pauses between steps use the outer flow’s scenario options instead of the nested flow’s.</p>",
      "<p><strong>Skip nested start URL navigation</strong> — when checked, the nested flow’s implicit <code>start_url</code> open (first step) is omitted (useful when the parent already opened the right page).</p>",
      "<p>Circular references (A→B→A) are rejected.</p>",
    ],
  },
  "step.if_present": {
    title: "If present (conditional)",
    body: [
      "<p>Waits for an element (same <strong>Find by</strong> options as a click). If it becomes visible within the timeout, Webbot runs every step in <strong>Then steps</strong>; otherwise it runs <strong>Else steps</strong>.</p>",
      "<p><strong>Then / Else branches</strong> are edited inline: use <strong>Add step</strong> under each branch to queue multiple steps — the same shapes as top-level steps. In raw JSON they are still <code>then_steps</code> / <code>else_steps</code> arrays. Unused branch steps are skipped in the live step list during a run.</p>",
      "<p><code>timeout_ms: 0</code> means no wait: Webbot checks visibility immediately.</p>",
    ],
  },
  "step.if_present.timeout": {
    title: "Visible timeout (if present)",
    body: [
      "<p>Milliseconds to wait for at least one matching element to be visible. On timeout, the <strong>Else</strong> branch runs.</p>",
    ],
  },
  "step.exit": {
    title: "Exit step",
    body: [
      "<p>Ends the scenario run successfully. No further steps in the flow are executed; the run completes without error.</p>",
      "<p>Use inside an <code>if_present</code> branch when one path should stop early.</p>",
    ],
  },
  "step.exit.message": {
    title: "Exit log message",
    body: ["<p>Optional line written to the run log when the exit step runs.</p>"],
  },
  "step.submit_form": {
    title: "Submit form step",
    body: [
      "<p>Fills one or more fields inside a form and submits. Respects the form’s HTML <code>method</code> (GET or POST).</p>",
      "<p>Add rows with <strong>+ field</strong>; each row is a locator plus value. Target the submit control by name or CSS selector.</p>",
    ],
  },
  "step.submit_form.method": {
    title: "Form method",
    body: [
      "<p><code>get</code> or <code>post</code>. Webbot checks this matches the form’s <code>method</code> attribute before submitting.</p>",
    ],
  },
  "step.submit_form.form_selector": {
    title: "Form CSS selector",
    body: [
      "<p>CSS selector for the <code>&lt;form&gt;</code> element, e.g. <code>#search-form</code> or <code>form.login</code>.</p>",
    ],
  },
  "step.submit_form.submit": {
    title: "Submit button",
    body: [
      "<p><strong>Submit button name</strong> — accessible name when using role-based submit.</p>",
      "<p><strong>Submit CSS selector</strong> — e.g. <code>button[type=submit]</code>.</p>",
    ],
  },
  "step.submit_form.fields": {
    title: "Form fields",
    body: [
      "<p>Each row: <strong>Find by</strong> + locator fields + <strong>Value</strong> to type before submit.</p>",
    ],
  },
  "locator.by": {
    title: "Find by",
    body: [
      "<p>How Playwright locates the element:</p>",
      helpTable(["Mode", "When to use"], [
        ["<code>role</code>", "ARIA role + accessible name (recommended for buttons and links)."],
        ["<code>text</code>", "Visible text on the page."],
        ["<code>css</code>", "CSS selector (<code>#id</code>, <code>.class</code>, etc.)."],
        [
          "<code>data</code>",
          "Any <code>data-*</code> attribute (e.g. <code>data-testid</code>, <code>data-cy</code>, <code>data-qa</code>).",
        ],
        ["<code>label</code>", "Text on the associated <code>&lt;label&gt;</code> (forms)."],
      ]),
    ],
  },
  "locator.role": {
    title: "Role",
    body: [
      "<p>ARIA role, e.g. <code>button</code>, <code>link</code>, <code>textbox</code>. Used with <strong>Accessible name</strong>.</p>",
    ],
  },
  "locator.name": {
    title: "Accessible name",
    body: [
      "<p>Visible label or <code>aria-label</code> text Playwright uses with the role locator.</p>",
    ],
  },
  "locator.text": {
    title: "Visible text",
    body: ["<p>Exact or partial visible text shown on the element or its children.</p>"],
  },
  "locator.selector": {
    title: "CSS selector",
    body: [
      "<p>Standard CSS, e.g. <code>#id</code>, <code>.class</code>, <code>button.submit</code>, <code>input[name=q]</code>.</p>",
    ],
  },
  "locator.data_attr": {
    title: "Data attribute",
    body: [
      "<p>Name of the HTML attribute on the element:</p>",
      helpTable(["You enter", "Matches"], [
        ["<code>data-testid</code>", "Standard test hook (same as legacy <code>test_id</code>)."],
        ["<code>data-cy</code>", "Common in Cypress-based apps."],
        ["<code>data-qa</code>", "QA / automation hooks."],
        ["<code>testid</code>", "Shorthand — normalized to <code>data-testid</code>."],
      ]),
    ],
  },
  "locator.data_value": {
    title: "Attribute value",
    body: [
      "<p>The exact string value of that attribute on the element, e.g. <code>login-submit</code> for <code>data-testid=\"login-submit\"</code>.</p>",
      "<p>Inspect the element in DevTools and copy the value inside the quotes.</p>",
    ],
  },
  "locator.label": {
    title: "Label text",
    body: ["<p>Text on the <code>&lt;label&gt;</code> associated with an input (good for forms).</p>"],
  },
  "locator.value": {
    title: "Value to type",
    body: ["<p>Text entered into the field for <code>fill</code> steps or form field rows.</p>"],
  },
};

/** Sidebar groups; topic order within each group is used for Previous / Next. */
const HELP_NAV = [
  { label: "Overview", topics: ["overview"] },
  {
    label: "Workspace",
    topics: ["help.home", "help.run", "help.flows"],
  },
  {
    label: "Run",
    topics: ["run.scenario", "run.loops", "run.pause", "run.headless"],
  },
  {
    label: "Builder",
    topics: [
      "builder.name",
      "builder.description",
      "builder.start_url",
      "builder.save",
      "builder.load",
      "builder.test_run",
      "builder.steps",
    ],
  },
  {
    label: "Scenario options",
    topics: [
      "scenario.options",
      "scenario.random_delay",
      "scenario.between_steps_min",
      "scenario.between_steps_max",
      "scenario.between_steps_distribution",
    ],
  },
  {
    label: "Step types",
    topics: [
      "step.types",
      "scenario.workflow_label",
      "step.open_url",
      "step.open_url.url",
      "step.goto",
      "step.goto.target",
      "step.click",
      "step.fill",
      "step.delay",
      "step.delay.min",
      "step.delay.max",
      "step.delay.distribution",
      "step.delay.long_pause",
      "step.scroll",
      "step.scroll.delta_y",
      "step.scroll.ticks",
      "step.scroll.overscroll",
      "step.scroll.after",
      "step.run_scenario",
      "step.if_present",
      "step.if_present.timeout",
      "step.exit",
      "step.exit.message",
      "step.submit_form",
      "step.submit_form.method",
      "step.submit_form.form_selector",
      "step.submit_form.submit",
      "step.submit_form.fields",
    ],
  },
  {
    label: "Locators",
    topics: [
      "locator.by",
      "locator.role",
      "locator.name",
      "locator.text",
      "locator.selector",
      "locator.data_attr",
      "locator.data_value",
      "locator.label",
      "locator.value",
    ],
  },
];
