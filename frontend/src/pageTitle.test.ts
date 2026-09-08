import { describe, expect, it } from "vitest";
import { APP_TITLE, formatPageTitle } from "./pageTitle";

describe("formatPageTitle", () => {
  it("joins screen name with the product mark", () => {
    expect(formatPageTitle("Дашборд")).toBe("Дашборд · AI Jewelry");
    expect(formatPageTitle("  Журнал документов ")).toBe("Журнал документов · AI Jewelry");
    expect(formatPageTitle("")).toBe(APP_TITLE);
  });
});
