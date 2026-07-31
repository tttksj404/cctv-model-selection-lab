import { createApp, defineComponent, h, nextTick, reactive } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import ConfirmModal from "./ConfirmModal.vue";

const mountedApps = [];

function mountModal(overrides = {}) {
  const state = reactive({
    open: true,
    reason: "",
    showReason: false,
    reasonError: "",
    error: "",
    loading: false,
    confirmDisabled: false,
    ...overrides
  });
  const onConfirm = vi.fn();
  const onClose = vi.fn();
  const root = document.createElement("div");
  document.body.append(root);

  const Host = defineComponent({
    setup() {
      return () => h(ConfirmModal, {
        open: state.open,
        title: "확인 제목",
        message: "확인 메시지",
        confirmText: "저장",
        showReason: state.showReason,
        reason: state.reason,
        reasonError: state.reasonError,
        error: state.error,
        loading: state.loading,
        confirmDisabled: state.confirmDisabled,
        "onUpdate:reason": (value) => { state.reason = value; },
        onConfirm,
        onClose
      });
    }
  });

  const app = createApp(Host);
  app.mount(root);
  mountedApps.push({ app, root });
  return { root, state, onConfirm, onClose };
}

afterEach(() => {
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount();
    root.remove();
  }
});

describe("ConfirmModal", () => {
  it("일반 확인 모달은 기본적으로 사유 입력을 숨긴다", () => {
    const { root, onConfirm } = mountModal();

    expect(root.querySelector("textarea")).toBeNull();
    const confirmButton = [...root.querySelectorAll("button")].find((button) => button.textContent === "저장");
    confirmButton.click();
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("선택적으로 사유 v-model, 오류, 비활성·로딩 상태를 제공한다", async () => {
    const { root, state, onConfirm, onClose } = mountModal({
      showReason: true,
      reasonError: "사유를 입력해 주세요.",
      confirmDisabled: true
    });

    const textarea = root.querySelector("textarea");
    expect(textarea).not.toBeNull();
    expect(root.textContent).toContain("사유를 입력해 주세요.");

    textarea.value = "상태 변경 근거";
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    await nextTick();
    expect(state.reason).toBe("상태 변경 근거");

    const confirmButton = [...root.querySelectorAll("button")].find((button) => button.textContent === "저장");
    expect(confirmButton.disabled).toBe(true);
    confirmButton.click();
    expect(onConfirm).not.toHaveBeenCalled();

    state.confirmDisabled = false;
    state.loading = true;
    await nextTick();
    expect(root.textContent).toContain("처리 중...");
    root.querySelector(".ghost-button").click();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("작업 실패 메시지를 모달 안에 표시한다", () => {
    const { root } = mountModal({ error: "상태 변경에 실패했습니다." });

    expect(root.querySelector('[role="alert"]').textContent).toBe("상태 변경에 실패했습니다.");
  });
});
