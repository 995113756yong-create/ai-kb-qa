import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import LanguageToggle from "@/components/LanguageToggle";
import { I18nProvider, useT, useI18n } from "@/lib/i18n";
import { LOCALE_STORAGE_KEY } from "@/lib/i18n/messages";

// Provider 行为：默认中文、读 localStorage、切换后写回、<html lang> 同步。

function Probe() {
  const t = useT();
  const { locale } = useI18n();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="send">{t("chat.send")}</span>
      <span data-testid="greet">{t("chat.emptyTitleWithAgent", { name: "教练" })}</span>
    </div>
  );
}

afterEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe("I18nProvider", () => {
  it("默认中文", () => {
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("zh");
    expect(screen.getByTestId("send").textContent).toBe("发送");
  });

  it("读取 localStorage 中的语言", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("en");
    expect(screen.getByTestId("send").textContent).toBe("Send");
  });

  it("占位符按语言替换", () => {
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("greet").textContent).toBe("向「教练」提问");
  });

  it("localStorage 里是非法值时回落到默认语言", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "fr");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("zh");
  });

  it("同步 <html lang>", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en");
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    );
    expect(document.documentElement.lang).toBe("en");
  });
});

describe("LanguageToggle", () => {
  it("点击在中文与英文之间切换，并写入 localStorage", async () => {
    render(
      <I18nProvider>
        <LanguageToggle />
        <Probe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("zh");

    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByTestId("locale").textContent).toBe("en");
    expect(screen.getByTestId("send").textContent).toBe("Send");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");

    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByTestId("locale").textContent).toBe("zh");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("zh");
  });
});