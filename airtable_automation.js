// Airtable Automation → "Run a script" action.
// Trigger: When a record is created in "Lead Requests".
//
// In the script step's LEFT panel, add these input variables (click "+ Add input variable"),
// each mapped to the trigger record's field:
//   count    -> field "Count"
//   location -> field "Location"
//   industry -> field "Industry"
//   country  -> field "Country code"   (optional)
//
// Then set the two constants below.
// IMPORTANT: FIRE_URL must be the API host (api.anthropic.com), NOT the claude.ai browser URL.
// The claude.ai/... address is Cloudflare-protected and returns a 403 "Just a moment" challenge.

const FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/YOUR_TRIGGER_ID/fire";
const FIRE_TOKEN = "PASTE_ROUTINE_TOKEN_HERE"; // the sk-ant-oat01-... token from "Generate token"

// `input` and `fetch` are globals in Airtable automation scripts — no require/import needed.
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
