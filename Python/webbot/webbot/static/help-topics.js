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
      "<p>Webbot runs human-like browser automation: curved mouse moves, variable delays, and a persistent profile.</p>",
      "<p>Use the top tabs to switch between <strong>Workspace</strong> (editor and log) and <strong>Flow groups</strong> (sidebar sections). Pick a flow in the sidebar, edit it on the right, and press <strong>Start</strong> or use <strong>Run group</strong> on a section. Flows can be JSON (step builder) or Python (editable source panel). Use <strong>run_scenario</strong> steps in JSON flows to compose subflows of either kind.</p>",
      "<p>Scenarios live under <code>%APPDATA%/webbot/scenarios/</code> on Windows (or <code>~/.config/webbot/scenarios/</code> elsewhere): <code>.json</code> for JSON flows and <code>.py</code> for Python flows (only one extension per flow name). Group membership is saved in <code>groups.json</code> in that folder.</p>",
    ],
  },
  "help.home": {
    title: "Workspace",
    body: [
      "<p>One screen: <strong>Flows</strong> and <strong>Run</strong> cards on the left, editor on the right, log at the bottom.</p>",
      helpTable(
        ["Area", "What it does"],
        [
          ["Flows card", "Flows grouped into collapsible sections plus ungrouped; pick one to edit."],
          ["New JSON / New Python / Groups / Delete", "Create JSON or Python drafts; <strong>Groups</strong> (or the <strong>Flow groups</strong> tab) edits sidebar sections; delete saved flows or discard a draft."],
          ["Run card", "Loops, pause between loops, pause between flows in a group, headless, Start/Stop."],
          ["Start / Stop", "Run the selected flow. Step progress appears in the editor column."],
          ["Editor", "JSON: name, URL, options, steps (drag to reorder). Python: monospace source editor; flow name is read-only once saved."],
          ["Save / Test run", "Save JSON or Python to disk, or save and run immediately."],
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
          ["Loops", "How many full passes through the flow."],
          ["Pause between loops", "Wait time after each full pass (except the last)."],
          ["Pause between flows in group", "Seconds to wait between flows when using Run group."],
          ["Headless", "Hide the browser window (faster; harder to debug)."],
          ["Flow preview", "Step list with live green/red status during a run."],
          ["Log", "Timestamped messages from the runner."],
        ]
      ),
      "<p>Use the sidebar in this dialog for details on each control.</p>",
    ],
  },
  "help.flows": {
    title: "Flows tab",
    body: [
      "<p>Create and edit flows: JSON in the step builder, or Python in the source editor (<strong>New Python</strong>).</p>",
      helpTable(
        ["Area", "What it does"],
        [
          ["Flow list", "Grouped sections and ungrouped flows; use Groups to edit membership."],
          ["Name / description / start URL", "Metadata; start URL is used when there is no <code>goto</code> step."],
          ["Scenario options", "Optional random delay between every step."],
          ["Steps", "Drag by the grip to reorder. Types: goto, click, fill, delay, scroll, submit_form, run_scenario (nested JSON or Python flow)."],
          ["Save / Test run", "Write JSON to disk, or save and start immediately."],
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
      "<p>Each loop is a full pass; step progress in the status bar shows <code>loop 2/5</code> when loops &gt; 1.</p>",
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
      "<p>If set and no <code>goto</code> step appears in the step list, Webbot opens this URL as step 1 before running your steps.</p>",
      "<p>If you already have a <code>goto</code> step, this field is not used automatically.</p>",
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
      "<p>When enabled, Webbot waits a random amount before each step after the first (including after an auto start-URL goto).</p>",
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
        ["<code>goto</code>", "Navigate to a URL."],
        ["<code>click</code>", "Human-like click on an element."],
        ["<code>fill</code>", "Type into one field."],
        ["<code>submit_form</code>", "Fill multiple fields and submit a form (GET or POST)."],
        ["<code>delay</code>", "Wait a random duration."],
        ["<code>scroll</code>", "Wheel scroll with optional overshoot."],
        ["<code>run_scenario</code>", "Run another saved JSON flow inline (same browser tab)."],
      ]),
    ],
  },
  "step.goto": {
    title: "Goto step",
    body: [
      "<p>Opens a URL in the current tab. Uses <code>domcontentloaded</code> and a short reading pause after load.</p>",
    ],
  },
  "step.goto.url": {
    title: "URL (goto)",
    body: [
      "<p>Full address including <code>https://</code>. Example: <code>https://example.com</code>.</p>",
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
      "<p><strong>Skip nested start URL goto</strong> — when checked, the nested flow’s implicit <code>start_url</code> navigation is omitted (useful when the parent already opened the right page).</p>",
      "<p>Circular references (A→B→A) are rejected.</p>",
    ],
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
      "step.goto",
      "step.goto.url",
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
