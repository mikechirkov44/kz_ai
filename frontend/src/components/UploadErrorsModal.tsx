import Modal from "./Modal";
import { uploadErrorSubtitle, type UploadErrorItem } from "../uploadErrors";

type Props = {
  open: boolean;
  processedRows: number;
  errors: UploadErrorItem[];
  onClose: () => void;
};

export default function UploadErrorsModal({ open, processedRows, errors, onClose }: Props) {
  return (
    <Modal
      open={open}
      wide
      title="Ошибки загрузки"
      subtitle={uploadErrorSubtitle(processedRows, errors)}
      onClose={onClose}
    >
      <div className="table-wrap upload-errors-table">
        <table>
          <thead>
            <tr>
              <th>Строка</th>
              <th>Поле</th>
              <th>Ошибка</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((err, idx) => (
              <tr key={`${err.row}-${err.field}-${idx}`}>
                <td>{err.row}</td>
                <td>{err.field}</td>
                <td>{err.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
