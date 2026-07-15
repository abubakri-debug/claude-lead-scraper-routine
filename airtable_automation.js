// Airtable Automation → "Run a script" action.
// Trigger: When a record is created in "Lead Requests".
// In the automation's script step, add input variables mapped from the trigger record:
//   count    -> field "Count"
//   location -> field "Location"
//   industry -> field "Industry"
//   country  -> field "Country code"  (optional)
// Then paste the routine Fire URL and token below (from SETUP_CHECKLIST step 5).

const FIRE_URL = "PASTE_ROUTINE_FIRE_URL_HERE";     // e.g. https://api.anthropic.com/v1/claude_code/routines/trig_01.../fire
const FIRE_TOKEN = "PASTE_ROUTINE_TOKEN_HERE";      // per-routine bearer token (shown once)

const input = require("@airtable/blocks/interface"); // not used; Airtable provides input via config
const cfg = input.config();

const count = cfg.count || 20;
const location = cfg.location || "";
const industry = cfg.industry || "";
const country = cfg.country || "de";

// The /fire endpoint only accepts {"text": "..."} — pack the params into one line the
// routine prompt knows how to parse.
const text = `count=${count}; location=${location}; industry=${industry}; country=${country}`;

const resp = await fetch(FIRE_URL, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${FIRE_TOKEN}`,
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "experimental-cc-routine-2026-04-01",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ text }),
});

const body = await resp.text();
console.log("fire status:", resp.status, body);
if (!resp.ok) {
  throw new Error(`Routine fire failed (${resp.status}): ${body}`);
}
