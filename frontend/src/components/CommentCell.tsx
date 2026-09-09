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
      <div className="tz-comment-row">
        {comment ? <p className="tz-comment-text">{comment}</p> : <span className="tz-comment-empty">—</span>}
        {canEdit && (
          <span className="tz-comment-actions no-print">
            <button className="tz-text-link" type="button" onClick={() => setOpen((v) => !v)}>
              {open ? "скрыть" : comment ? "изменить" : "добавить"}
            </button>
            {onShowHistory && (
              <button className="tz-text-link" type="button" onClick={onShowHistory}>
                история
              </button>
            )}
          </span>
        )}
      </div>
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
