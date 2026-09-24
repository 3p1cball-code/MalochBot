const { chromium } = require("playwright-core");

const [, , url, out, w, h, mode] = process.argv;

(async () => {
  const browser = await chromium.launch({
    executablePath: "/usr/bin/brave-browser",
    headless: true,
    args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage({
    viewport: { width: parseInt(w || "1700", 10), height: parseInt(h || "1000", 10) },
  });
  await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(900);
  if (mode && mode.startsWith("clickfull:")) {
    await page.click(mode.slice(10));
    await page.waitForTimeout(700);
    await page.screenshot({ path: out, fullPage: true });
  } else if (mode && mode.startsWith("click:")) {
    await page.click(mode.slice(6));
    await page.waitForTimeout(700);
    await page.screenshot({ path: out });
  } else {
    await page.screenshot({ path: out, fullPage: mode === "full" });
  }
  await browser.close();
  console.log("saved", out);
})().catch((err) => {
  console.error("ERR", err.message);
  process.exit(1);
});
