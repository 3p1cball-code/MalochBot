const { chromium } = require("playwright-core");
const path = require("path");

const BASE = process.env.MB_URL || "http://192.168.33.24:8765";
const OUT = process.env.MB_OUT || path.join(__dirname, "..", "docs", "screenshots");
const W = 1700, H = 1000;

// Macht Firmennamen und personenbezogene Inhalte unkenntlich.
const BLUR = `
  table.jobs-table td.co,
  #job-detail .subtitle strong,
  #job-detail p:not(.subtitle),
  #job-detail .timeline .tl-text,
  .docs-table td a,
  .docs-table .eval-box pre,
  textarea[name="profile"],
  textarea[name="preferences"],
  textarea[name="search_extra"],
  input[name="mail_email"],
  input[name="mail_host"],
  input[name="mail_folders"] { filter: blur(5px) !important; }
`;

const shots = [
  { name: "01-jobs-dark", p: "/", theme: "dunkel" },
  { name: "02-jobs-dark-detail", p: "/", theme: "dunkel", detail: true },
  { name: "03-jobs-dark-filter-remote", p: "/", theme: "dunkel", filter: { remote: true, fit: 70 } },
  { name: "04-jobs-dark-filter-status", p: "/", theme: "dunkel", filter: { statuses: ["interview", "angebot", "beworben"] } },
  { name: "05-jobs-light", p: "/", theme: "hell" },
  { name: "06-stats-dark", p: "/stats", theme: "dunkel", full: true },
  { name: "07-stats-light", p: "/stats", theme: "hell", full: true },
  { name: "08-documents-dark", p: "/documents", theme: "dunkel", full: true },
  { name: "09-documents-light", p: "/documents", theme: "hell", full: true },
  { name: "10-settings-dark", p: "/settings", theme: "dunkel", full: true },
  { name: "11-about-dark", p: "/about", theme: "dunkel", full: true },
  { name: "12-about-light", p: "/about", theme: "hell", full: true },
  { name: "13-log-dark", p: "/log", theme: "dunkel" },
  { name: "14-jobs-dark-actions", p: "/", theme: "dunkel", detail: true, scrollDetail: true, full: true },
];

(async () => {
  const browser = await chromium.launch({
    executablePath: "/usr/bin/brave-browser",
    headless: true,
    args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
  });
  for (const s of shots) {
    const ctx = await browser.newContext({ viewport: { width: W, height: H } });
    await ctx.addInitScript((t) => { try { localStorage.setItem("mb-theme", t); } catch (e) {} }, s.theme);
    const page = await ctx.newPage();
    await page.goto(BASE + s.p, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(900);
    if (s.detail) {
      await page.evaluate(() => {
        const j = (window.MB_JOBS || []).find((x) => x.cover_letter_name) || (window.MB_JOBS || [])[0];
        if (j && window.mbShowDetail) window.mbShowDetail(j.id);
      });
      await page.waitForTimeout(400);
    }
    if (s.filter) {
      await page.evaluate((f) => {
        if (f.statuses) {
          document.querySelectorAll(".f-status").forEach((c) => { c.checked = f.statuses.indexOf(c.value) >= 0; });
        }
        if (f.remote) { const r = document.getElementById("f-remote"); if (r) r.value = "1"; }
        if (f.fit) { const el = document.getElementById("f-fit"); if (el) el.value = String(f.fit); }
        ["f-remote", "f-fit"].forEach((id) => { const e = document.getElementById(id); if (e) e.dispatchEvent(new Event("input", { bubbles: true })); });
        document.querySelectorAll(".f-status").forEach((c) => c.dispatchEvent(new Event("change", { bubbles: true })));
      }, s.filter);
      await page.waitForTimeout(400);
    }
    await page.addStyleTag({ content: BLUR });
    if (s.scrollDetail) {
      await page.evaluate(() => {
        const d = document.getElementById("job-detail");
        if (d) { d.style.position = "static"; d.style.maxHeight = "none"; }
      });
      await page.waitForTimeout(300);
    }
    const out = path.join(OUT, s.name + ".png");
    await page.screenshot({ path: out, fullPage: !!s.full });
    console.log("saved", out);
    await ctx.close();
  }
  await browser.close();
})().catch((e) => { console.error("ERR", e.message); process.exit(1); });
