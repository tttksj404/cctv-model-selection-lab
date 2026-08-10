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
    const scenarioPendingVisible = await page.evaluate(() => {
      const select = document.querySelector("#scenario-select");
      select.focus();
      select.value = "uncertain";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      return document.querySelector("#app")?.getAttribute("aria-busy") === "true";
    });
    await page.getByText(/관할 내 질량 66\.0%/).waitFor();
    const scenarioPendingCleared = (await page.locator("#app").getAttribute("aria-busy")) === "false";
    const scenarioFocusRestored = await page.locator("#scenario-select").evaluate(
      (element) => document.activeElement === element,
    );
    const confirmDisabledWithoutCandidate = await page
      .getByRole("button", { name: "후보 확정" })
      .isDisabled();
    await page.locator("#scenario-select").selectOption("outside_zero");
    await page.locator('[data-jurisdiction-status="outside_dominant"]').waitFor();
    const zeroMassStatusVisible = await page
      .locator('[data-jurisdiction-status="outside_dominant"]')
      .isVisible();
    const zeroMassStateVisible = await page.getByText("상태 관할 이탈 우세", { exact: false }).isVisible();
    const zeroMassNextCameraBlocked = await page
      .getByText("관할 내 질량 기준 미달 · 자동 카메라 추천 없음", { exact: true })
      .isVisible();
    const zeroMassCameraRankingSuppressed = await page
      .locator('[data-camera-ranking-state="suppressed"]')
      .isVisible();
    const zeroMassCameraRankingAvailable =
      (await page.locator('[data-camera-ranking-state="available"]').count()) === 0;
    const zeroMassZoneRankLabels = await page.locator(".zone-rank").allTextContents();
    const zeroMassZoneRanksSuppressed =
      zeroMassZoneRankLabels.length === 4 &&
      zeroMassZoneRankLabels.every((label) => label === "동률 · 순위 보류");
    const zeroMassAutoSelectionAbsent = await page.locator("[data-zone-id]").evaluateAll(
      (elements) => elements.every((element) => element.getAttribute("aria-pressed") === "false"),
    );
    const zeroMassArgmaxAbsent = (await page.getByText("자동 · Argmax", { exact: true }).count()) === 0;
    const zeroMassZoneProbabilities = await page.locator(".probability-value").evaluateAll(
      (elements) => elements.map((element) => element.textContent),
    );
    const zeroMassLayout = await page.evaluate(() => {
      const root = document.documentElement;
      const statusCard = document.querySelector('[data-jurisdiction-status="outside_dominant"]');
      const bounds = statusCard?.getBoundingClientRect();
      return {
        viewportWidth: root.clientWidth,
        rootScrollWidth: root.scrollWidth,
        bodyScrollWidth: document.body.scrollWidth,
        statusLeft: bounds?.left ?? 0,
        statusRight: bounds?.right ?? 0,
      };
    });
    const zeroMassNoHorizontalOverflow =
      zeroMassLayout.rootScrollWidth <= zeroMassLayout.viewportWidth &&
      zeroMassLayout.bodyScrollWidth <= zeroMassLayout.viewportWidth &&
      zeroMassLayout.statusLeft >= -1 &&
      zeroMassLayout.statusRight <= zeroMassLayout.viewportWidth + 1;
    const zeroMassScreenshotPath = `${captureDirectory}${viewport.name}-outside-zero.png`;
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: zeroMassScreenshotPath, fullPage: true });
    await page.locator("#scenario-select").selectOption("unknown_zero");
    await page.locator('[data-jurisdiction-status="unknown_dominant"]').waitFor();
    const unknownRecommendationVisible = await page
      .getByText("보류 · 정보 부족 우세", { exact: true })
      .isVisible();
    const unknownStatusVisible = await page
      .locator('[data-jurisdiction-status="unknown_dominant"]')
      .isVisible();
    await page.locator("#scenario-select").selectOption("outside");
    await page.getByText(/관할 밖 55\.0%/).waitFor();
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
    await page.getByText(/관할 내 질량 78\.0%/).waitFor();
    await page.getByRole("button", { name: "후보 확정" }).click();
    await page.waitForFunction(
      () => document.querySelector('[data-decision="confirm"]')?.classList.contains("selected"),
    );
    const decisionPressed = await page
      .getByRole("button", { name: "후보 확정" })
      .getAttribute("aria-pressed");
    const decisionFocusRestored = await page
      .getByRole("button", { name: "후보 확정" })
      .evaluate((element) => document.activeElement === element);
    await page.getByRole("button", { name: /4구역, 관할 내 존재/ }).click();
    await page.waitForFunction(
      () => document.querySelector('[data-zone-id="4"]')?.getAttribute("aria-pressed") === "true",
    );
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
      !scenarioPendingVisible ||
      !scenarioPendingCleared ||
      !scenarioFocusRestored ||
      !confirmDisabledWithoutCandidate ||
      !zeroMassStatusVisible ||
      !zeroMassStateVisible ||
      !zeroMassNextCameraBlocked ||
      !zeroMassCameraRankingSuppressed ||
      !zeroMassCameraRankingAvailable ||
      !zeroMassZoneRanksSuppressed ||
      !zeroMassAutoSelectionAbsent ||
      !zeroMassArgmaxAbsent ||
      zeroMassZoneProbabilities.some((value) => value !== "25.0%") ||
      !zeroMassNoHorizontalOverflow ||
      !unknownRecommendationVisible ||
      !unknownStatusVisible ||
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
      scenarioPendingVisible,
      scenarioPendingCleared,
      scenarioFocusRestored,
      confirmDisabledWithoutCandidate,
      zeroMassStatusVisible,
      zeroMassStateVisible,
      zeroMassNextCameraBlocked,
      zeroMassCameraRankingSuppressed,
      zeroMassCameraRankingAvailable,
      zeroMassZoneRanksSuppressed,
      zeroMassZoneRankLabels,
      zeroMassAutoSelectionAbsent,
      zeroMassArgmaxAbsent,
      zeroMassZoneProbabilities,
      zeroMassLayout,
      zeroMassNoHorizontalOverflow,
      zeroMassScreenshotPath,
      unknownRecommendationVisible,
      unknownStatusVisible,
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
    await page.evaluate(() => {
      const select = document.querySelector("#scenario-select");
      select.value = "__missing__";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await page.getByText("화면 초기화 실패", { exact: true }).waitFor();
    const latestErrorVisible = await page.getByText("화면 초기화 실패", { exact: true }).isVisible();
    const latestErrorBusyCleared = (await page.locator("#app").getAttribute("aria-busy")) === "false";
    if (!latestErrorVisible || !latestErrorBusyCleared) {
      throw new Error(`${viewport.name}: latest error flow failed`);
    }
    checks[checks.length - 1].latestErrorVisible = latestErrorVisible;
    checks[checks.length - 1].latestErrorBusyCleared = latestErrorBusyCleared;
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

