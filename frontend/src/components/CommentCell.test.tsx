import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import CommentCell from "./CommentCell";

function mount(props: Partial<ComponentProps<typeof CommentCell>> = {}) {
  const onDraftChange = props.onDraftChange ?? vi.fn();
  const onSave = props.onSave ?? vi.fn();
  return render(
    <table>
      <tbody>
        <tr>
          <CommentCell
            comment={props.comment ?? null}
            draft={props.draft ?? ""}
            saving={props.saving ?? false}
            canEdit={props.canEdit}
            onDraftChange={onDraftChange}
            onSave={onSave}
            onShowHistory={props.onShowHistory}
          />
        </tr>
      </tbody>
    </table>,
  );
}

describe("CommentCell", () => {
  it("shows preview without an editor", () => {
    const { container } = mount({ comment: "Уже есть", canEdit: true, onShowHistory: vi.fn() });
    expect(screen.getByText("Уже есть")).toBeTruthy();
    expect(screen.queryByPlaceholderText("Новый комментарий")).toBeNull();
    expect(container).toMatchSnapshot();
  });

  it("opens the editor on click", () => {
    const onDraftChange = vi.fn();
    const onSave = vi.fn();
    mount({ comment: null, canEdit: true, draft: "текст", onDraftChange, onSave, onShowHistory: vi.fn() });
    fireEvent.click(screen.getByRole("button", { name: "добавить" }));
    expect(screen.getByPlaceholderText("Новый комментарий")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(onSave).toHaveBeenCalled();
  });
});
