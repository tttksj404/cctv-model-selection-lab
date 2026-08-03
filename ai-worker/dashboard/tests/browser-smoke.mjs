import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { preview } from "vite";

const server = await preview({
  preview: { host: "127.0.0.1", port: 4174, strictPort: true },
});
const browser = await chromium.launch({ channel: "chrome", headless: true });
const errors = [];
const externalRequests = [];
const networkApiRequests = [];
const checks = [];
const captureDirectory = fileURLToPath(new URL("../tmp/dashboard-qa/", import.meta.url));
mkdirSync(captureDirectory, { recursive: true });

try {
  for (const viewport of [
    { name: "desktop", width: 1280, height: 900 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "mobile", width: 375, height: 812 },
  ]) {
    const page = await browser.newPage({ viewport });
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(`${viewport.name}: ${message.text()}`);
    });
    page.on("pageerror", (error) => errors.push(`${viewport.name}: ${error.message}`));
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.hostname !== "127.0.0.1") externalRequests.push(request.url());
      if (["fetch", "xhr", "websocket", "eventsource"].includes(request.resourceType())) {
        networkApiRequests.push(`${request.resourceType()}:${request.url()}`);
      }
    });

    await page.goto("http://127.0.0.1:4174/", { waitUntil: "networkidle" });
    const mockBadge = await page.getByText("Mock 고정", { exact: true }).isVisible();
    const dispatchDisabled = await page
      .getByRole("button", { name: /연결 비활성/ })
      .isDisabled();
    const sealedAccuracyVisible = await page.getByText("91.88%", { exact: true }).isVisible();
    const gateVisible = await page
      .getByText("합성 proxy 통과 · 운영 미승격", { exact: true })
      .isVisible();
    await page.locator("#scenario-select").selectOption("uncertain");
    const scenarioFocusRestored = await page.locator("#scenario-select").evaluate(
      (element) => document.activeElement === element,
    );
    const confirmDisabledWithoutCandidate = await page
      .getByRole("button", { name: "후보 확정" })
      .isDisabled();
    await page.locator("#scenario-select").selectOption("outside");
    const outsideRecommendationBlocked = await page
      .getByText("보류 · 관할 이탈 우세", { exact: true })
      .isVisible();
    const outsideMassVisible = await page.getByText(/관할 밖 55\.0%/).isVisible();
    const outsideNextCameraBlocked = await page
      .getByText("관할 내 질량 기준 미달 · 자동 카메라 추천 없음", { exact: true })
      .isVisible();
    const outsideArgmaxAbsent = (await page.getByText("자동 · Argmax", { exact: true }).count()) === 0;
    const outsideNextBadgeAbsent = (await page.getByText("다음", { exact: true }).count()) === 0;
    const outsideAutoSelectionAbsent = await page.locator("[data-zone-id]").evaluateAll(
      (elements) => elements.every((element) => element.getAttribute("aria-pressed") === "false"),
    );
    await page.locator("#scenario-select").selectOption("certain");
    await page.getByRole("button", { name: "후보 확정" }).click();
    const decisionPressed = await page
      .getByRole("button", { name: "후보 확정" })
      .getAttribute("aria-pressed");
    const decisionFocusRestored = await page
      .getByRole("button", { name: "후보 확정" })
      .evaluate((element) => document.activeElement === element);
    await page.getByRole("button", { name: /4구역, 관할 내 존재/ }).click();
    const zoneFocusRestored = await page
      .getByRole("button", { name: /4구역, 관할 내 존재/ })
      .evaluate((element) => document.activeElement === element);
    const confirmDisabledOutsideCandidateZone = await page
      .getByRole("button", { name: "후보 확정" })
      .isDisabled();
    const manualViewVisible = await page.getByText("현재 열람 · 후보 없음", {
      exact: true,
    }).isVisible();
    const selectedZone = await page
      .getByRole("button", { name: /4구역, 관할 내 존재/ })
      .getAttribute("aria-pressed");
    const localDecision = await page
      .getByRole("button", { name: "후보 확정" })
      .evaluate((element) => element.classList.contains("selected"));
    if (
      !mockBadge ||
      !dispatchDisabled ||
      !sealedAccuracyVisible ||
      !gateVisible ||
      !scenarioFocusRestored ||
      !confirmDisabledWithoutCandidate ||
      !outsideRecommendationBlocked ||
      !outsideMassVisible ||
      !outsideNextCameraBlocked ||
      !outsideArgmaxAbsent ||
      !outsideNextBadgeAbsent ||
      !outsideAutoSelectionAbsent ||
      decisionPressed !== "true" ||
      !decisionFocusRestored ||
      !zoneFocusRestored ||
      !confirmDisabledOutsideCandidateZone ||
      !manualViewVisible ||
      selectedZone !== "true" ||
      localDecision
    ) {
      throw new Error(`${viewport.name}: offline dashboard interaction failed`);
    }
    const screenshotPath = `${captureDirectory}${viewport.name}.png`;
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: screenshotPath, fullPage: true });
    checks.push({
      viewport: viewport.name,
      dispatchDisabled,
      selectedZone,
      sealedAccuracyVisible,
      gateVisible,
      scenarioFocusRestored,
      confirmDisabledWithoutCandidate,
      outsideRecommendationBlocked,
      outsideMassVisible,
      outsideNextCameraBlocked,
      outsideArgmaxAbsent,
      outsideNextBadgeAbsent,
      outsideAutoSelectionAbsent,
      decisionPressed,
      decisionFocusRestored,
      zoneFocusRestored,
      confirmDisabledOutsideCandidateZone,
      manualViewVisible,
      screenshotPath,
    });
    await page.close();
  }
  if (errors.length > 0) throw new Error(`browser errors: ${JSON.stringify(errors)}`);
  if (externalRequests.length > 0) {
    throw new Error(`unexpected external requests: ${JSON.stringify(externalRequests)}`);
  }
  if (networkApiRequests.length > 0) {
    throw new Error(`unexpected network API requests: ${JSON.stringify(networkApiRequests)}`);
  }
  process.stdout.write(
    `${JSON.stringify({ status: "passed", checks, errors, externalRequests, networkApiRequests })}\n`,
  );
} finally {
  await browser.close();
  await server.close();
}
