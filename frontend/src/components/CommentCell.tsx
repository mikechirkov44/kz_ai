import { useState } from "react";

type Props = {
  comment: string | null;
  draft: string;
  saving: boolean;
  canEdit?: boolean;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onShowHistory?: () => void;
};

export default function CommentCell({
  comment,
  draft,
  saving,
  canEdit,
  onDraftChange,
  onSave,
  onShowHistory,
}: Props) {
  const [open, setOpen] = useState(false);

  return (
    <td className="tz-comment tz-comment-compact">
      {comment ? <p className="tz-comment-text">{comment}</p> : <p className="tz-comment-empty">—</p>}
      {canEdit && (
        <div className="tz-comment-actions no-print">
          <button className="btn secondary sm" type="button" onClick={() => setOpen((v) => !v)}>
            {open ? "Скрыть" : comment ? "Комментарий" : "Добавить"}
          </button>
          {onShowHistory && (
            <button className="btn secondary sm" type="button" onClick={onShowHistory}>
              История
            </button>
          )}
        </div>
      )}
      {canEdit && open && (
        <div className="tz-comment-edit no-print">
          <textarea
            className="control"
            rows={2}
            placeholder="Новый комментарий"
            value={draft}
            onChange={(e) => onDraftChange(e.target.value)}
          />
          <button className="btn sm" type="button" disabled={saving || !draft.trim()} onClick={onSave}>
            {saving ? "…" : "Сохранить"}
          </button>
        </div>
      )}
    </td>
  );
}
