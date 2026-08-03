import { createApp, defineComponent, h, nextTick, reactive } from "vue";
import { afterEach, describe, expect, it } from "vitest";
import AppearancePicker from "./AppearancePicker.vue";

const APPEARANCE_KEYS = [
  "head",
  "face",
  "top",
  "bottom",
  "shoes",
  "accessory",
  "body",
  "feature"
];

const mountedApps = [];

function appearance(overrides = {}) {
  return {
    head: "",
    face: "",
    top: "",
    bottom: "",
    shoes: "",
    accessory: "",
    body: "",
    feature: "",
    ...overrides
  };
}

async function flushUi() {
  await Promise.resolve();
  await nextTick();
  await Promise.resolve();
}

async function mountPicker({ modelValue = appearance(), disabled = false, errors = {} } = {}) {
  const state = reactive({
    modelValue: { ...modelValue },
    disabled,
    errors: { ...errors }
  });
  const updates = [];
  const root = document.createElement("div");
  document.body.append(root);

  const Host = defineComponent({
    setup() {
      return () => h(AppearancePicker, {
        modelValue: state.modelValue,
        disabled: state.disabled,
        errors: state.errors,
        "onUpdate:modelValue": (value) => {
          const snapshot = { ...value };
          updates.push(snapshot);
          state.modelValue = snapshot;
        }
      });
    }
  });

  const app = createApp(Host);
  app.mount(root);
  mountedApps.push({ app, root });
  await flushUi();

  return { root, state, updates };
}

afterEach(() => {
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount();
    root.remove();
  }
});

function pickerRoot(root) {
  return root.querySelector('[data-testid="appearance-picker"]');
}

function category(root, key) {
  return root.querySelector(`[data-appearance-category="${key}"]`);
}

function feature(root, key, label) {
  return root.querySelector(
    `[data-appearance-feature="${label}"][data-category="${key}"]`
  );
}

function property(root, name, label) {
  return root.querySelector(
    `[data-appearance-property="${name}"][data-feature="${label}"]`
  );
}

function note(root, key) {
  return root.querySelector(`[data-appearance-note="${key}"]`);
}

async function click(element) {
  expect(element).not.toBeNull();
  element.click();
  await flushUi();
}

async function setValue(element, value) {
  expect(element).not.toBeNull();
  element.value = value;
  element.dispatchEvent(new Event(
    element.tagName === "SELECT" ? "change" : "input",
    { bubbles: true }
  ));
  await flushUi();
}

describe("AppearancePicker", () => {
  it("한 번에 하나의 인상착의 항목만 연다", async () => {
    const { root, updates } = await mountPicker();

    expect(pickerRoot(root)).not.toBeNull();
    expect(category(root, "head").getAttribute("aria-expanded")).toBe("false");
    expect(category(root, "top").getAttribute("aria-expanded")).toBe("false");

    await click(category(root, "head"));
    expect(category(root, "head").getAttribute("aria-expanded")).toBe("true");
    expect(category(root, "top").getAttribute("aria-expanded")).toBe("false");
    expect(root.querySelectorAll('[data-appearance-category][aria-expanded="true"]')).toHaveLength(1);

    await click(category(root, "top"));
    expect(category(root, "head").getAttribute("aria-expanded")).toBe("false");
    expect(category(root, "top").getAttribute("aria-expanded")).toBe("true");
    expect(root.querySelectorAll('[data-appearance-category][aria-expanded="true"]')).toHaveLength(1);
    expect(updates).toHaveLength(0);
  });

  it("복수 특징과 형태·색상을 현재 필드에 직렬화하고 나머지 키를 보존한다", async () => {
    const initial = appearance({
      head: "모자",
      face: "안경",
      shoes: "운동화",
      accessory: "백팩",
      body: "보통 체형",
      feature: "왼팔 문신"
    });
    const { root, state, updates } = await mountPicker({ modelValue: initial });

    await click(category(root, "top"));
    await click(feature(root, "top", "티셔츠"));
    await click(feature(root, "top", "셔츠"));
    await setValue(property(root, "form", "티셔츠"), "긴팔");
    await setValue(property(root, "color", "티셔츠"), "검정");

    const expected = appearance({
      ...initial,
      top: "티셔츠 (긴팔, 검정), 셔츠"
    });
    expect(updates.at(-1)).toEqual(expected);
    expect(state.modelValue).toEqual(expected);
    expect(Object.keys(updates.at(-1))).toEqual(APPEARANCE_KEYS);
  });

  it("화면용 '선택 안 함'과 속성용 '안함'을 모델에 내보내지 않는다", async () => {
    const { root, updates } = await mountPicker();

    expect(root.textContent).toContain("선택 안 함");
    await click(category(root, "head"));
    expect(updates).toHaveLength(0);

    await click(feature(root, "head", "모자"));
    expect([...root.querySelectorAll("option")].some((option) => option.value === "안함")).toBe(false);
    await click(feature(root, "head", "모자"));

    expect(updates.at(-1).head).toBe("");
    for (const update of updates) {
      expect(JSON.stringify(update)).not.toContain("선택 안 함");
      expect(Object.values(update)).not.toContain("안함");
    }
  });

  it("해석할 수 없는 기존 자유문자를 직접 입력으로 복원하고 마운트 시 emit하지 않는다", async () => {
    const legacyValue = "갈색 장발, 오른쪽 눈썹 위의 오래된 흉터";
    const { root, updates } = await mountPicker({
      modelValue: appearance({ head: legacyValue })
    });

    expect(updates).toHaveLength(0);
    expect(root.textContent).toContain(legacyValue);
    await click(category(root, "head"));

    expect(note(root, "head").value).toBe(legacyValue);
    expect(updates).toHaveLength(0);
  });

  it("입력 중인 공백은 model echo로 정규화하지 않는다", async () => {
    const { root, state } = await mountPicker();
    await click(category(root, "head"));

    await setValue(note(root, "head"), "검은 머리 ");

    expect(note(root, "head").value).toBe("검은 머리 ");
    expect(state.modelValue.head).toBe("검은 머리");
  });

  it("생성한 문자열을 선택 칩과 형태·색상 컨트롤로 복원한다", async () => {
    const { root, updates } = await mountPicker({
      modelValue: appearance({
        top: "티셔츠 (긴팔, 검정), 셔츠 (반팔, 흰색)"
      })
    });

    await click(category(root, "top"));

    expect(feature(root, "top", "티셔츠").getAttribute("aria-pressed")).toBe("true");
    expect(feature(root, "top", "셔츠").getAttribute("aria-pressed")).toBe("true");
    expect(feature(root, "top", "후드티").getAttribute("aria-pressed")).toBe("false");
    expect(property(root, "form", "티셔츠").value).toBe("긴팔");
    expect(property(root, "color", "티셔츠").value).toBe("검정");
    expect(property(root, "form", "셔츠").value).toBe("반팔");
    expect(property(root, "color", "셔츠").value).toBe("흰색");
    expect(updates).toHaveLength(0);
  });

  it("선택 특징 삭제와 직접 입력 지우기를 빈 문자열로 emit한다", async () => {
    const { root, state, updates } = await mountPicker({
      modelValue: appearance({
        head: "오른쪽 귀 위 흉터",
        shoes: "운동화 (검정)"
      })
    });

    await click(category(root, "shoes"));
    await click(root.querySelector('[data-appearance-remove][data-feature="운동화"]'));
    expect(updates.at(-1).shoes).toBe("");
    expect(updates.at(-1).head).toBe("오른쪽 귀 위 흉터");

    await click(category(root, "head"));
    await setValue(note(root, "head"), "");
    expect(updates.at(-1).head).toBe("");
    expect(updates.at(-1).shoes).toBe("");
    expect(state.modelValue).toEqual(appearance());
  });

  it("외부 modelValue 변경을 열린 패널에 다시 반영하며 emit하지 않는다", async () => {
    const { root, state, updates } = await mountPicker();
    await click(category(root, "top"));

    state.modelValue = appearance({
      face: "수염",
      top: "티셔츠 (긴팔, 남색)"
    });
    await flushUi();

    expect(feature(root, "top", "티셔츠").getAttribute("aria-pressed")).toBe("true");
    expect(property(root, "form", "티셔츠").value).toBe("긴팔");
    expect(property(root, "color", "티셔츠").value).toBe("남색");
    expect(note(root, "top").value).toBe("");
    expect(updates).toHaveLength(0);

    state.modelValue = appearance({ top: "목 부분에 직접 그린 무늬" });
    await flushUi();

    expect(feature(root, "top", "티셔츠").getAttribute("aria-pressed")).toBe("false");
    expect(note(root, "top").value).toBe("목 부분에 직접 그린 무늬");
    expect(updates).toHaveLength(0);
  });

  it("disabled여도 항목 내용은 열람하고 편집 컨트롤은 모두 비활성화한다", async () => {
    const { root, state, updates } = await mountPicker({
      modelValue: appearance({ top: "티셔츠 (긴팔, 검정)" })
    });
    await click(category(root, "top"));

    state.disabled = true;
    await flushUi();

    expect(category(root, "face").disabled).toBe(false);
    await click(category(root, "face"));
    await click(category(root, "top"));

    const controls = [...root.querySelectorAll('[data-appearance-panel="top"] button, [data-appearance-panel="top"] input, [data-appearance-panel="top"] textarea, [data-appearance-panel="top"] select')];
    expect(controls.length).toBeGreaterThan(3);
    expect(controls.every((control) => control.disabled)).toBe(true);

    feature(root, "top", "셔츠").click();
    await flushUi();
    expect(updates).toHaveLength(0);
  });

  it("필드별 남은 글자 수와 즉시 초과 오류 및 errors prop을 표시한다", async () => {
    const externalError = "얼굴 항목을 다시 확인해 주세요.";
    const { root } = await mountPicker({ errors: { face: externalError } });

    expect(root.querySelector('[data-appearance-error="face"]').textContent).toContain(externalError);

    await click(category(root, "head"));
    expect(root.querySelector('[data-appearance-remaining="head"]').textContent).toContain("255");
    await setValue(note(root, "head"), "가나다");
    expect(root.querySelector('[data-appearance-count="head"]').textContent).toContain("3");
    expect(root.querySelector('[data-appearance-remaining="head"]').textContent).toContain("252");

    await setValue(note(root, "head"), "가".repeat(256));
    expect(root.querySelector('[data-appearance-count="head"]').textContent).toContain("256");
    expect(root.querySelector('[data-appearance-remaining="head"]').textContent).toContain("1자 초과");
    expect(root.querySelector('[data-appearance-error="head"]').textContent).toMatch(/255|초과/);

    await click(category(root, "accessory"));
    expect(root.querySelector('[data-appearance-remaining="accessory"]').textContent).toContain("1000");
    await click(category(root, "feature"));
    expect(root.querySelector('[data-appearance-remaining="feature"]').textContent).toContain("2000");
  });

  it("카테고리 확장 상태와 특징 선택 상태를 ARIA 속성으로 제공한다", async () => {
    const { root } = await mountPicker({
      modelValue: appearance({ head: "모자 (검정)" })
    });

    expect(category(root, "head").getAttribute("aria-expanded")).toBe("false");
    await click(category(root, "head"));

    expect(category(root, "head").getAttribute("aria-expanded")).toBe("true");
    expect(feature(root, "head", "모자").getAttribute("aria-pressed")).toBe("true");
    expect(feature(root, "head", "긴머리").getAttribute("aria-pressed")).toBe("false");

    await click(feature(root, "head", "긴머리"));
    expect(feature(root, "head", "긴머리").getAttribute("aria-pressed")).toBe("true");

    await click(category(root, "face"));
    expect(category(root, "head").getAttribute("aria-expanded")).toBe("false");
    expect(category(root, "face").getAttribute("aria-expanded")).toBe("true");
  });
});
