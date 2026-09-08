import { FormEvent, useState } from "react";
import { api, Counterparty } from "../api";
import {
  buildManualRows,
  ManualLine,
  needsSalePrice,
  needsStockDate,
  newManualLine,
} from "../manualUpload";
import ArticleSelect from "./ArticleSelect";
import CounterpartySelect from "./CounterpartySelect";
import DatePicker from "./DatePicker";
import NumberField from "./NumberField";
import Select from "./Select";
import { MONTH_OPTIONS, yearOptions } from "../months";

type UploadResult = {
  status: string;
  processed_rows: number;
  errors: { row: number; field: string; message: string }[];
  upload_id: string;
};

type Props = {
  onSuccess: (result: UploadResult) => void;
};

const TYPE_OPTIONS = [
  { value: "sales", label: "Продажи" },
  { value: "stocks", label: "Остатки" },
  { value: "both", label: "Продажи + Остатки" },
  { value: "promo_motivation", label: "Доп. мотивация" },
];

export default function ManualUploadForm({ onSuccess }: Props) {
  const [cpId, setCpId] = useState("");
  const [cpName, setCpName] = useState("");
  const [shops, setShops] = useState<string[]>([]);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [uploadType, setUploadType] = useState("sales");
  const [stockDate, setStockDate] = useState("");
  const [lines, setLines] = useState<ManualLine[]>([newManualLine()]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const showPrice = needsSalePrice(uploadType);
  const stockRequired = needsStockDate(uploadType);
  const shopOptions = [{ value: "", label: "—" }, ...shops.map((shop) => ({ value: shop, label: shop }))];

  function onPickCounterparty(cp: Counterparty | null) {
    setCpName(cp?.name || "");
    setShops(cp?.shops || []);
    setLines((prev) => prev.map((line) => ({ ...line, shop: "" })));
  }

  function updateLine(key: string, patch: Partial<ManualLine>) {
    setLines((prev) => prev.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (stockRequired && !stockDate) {
      setError("Для остатков укажите дату");
      return;
    }
    const built = buildManualRows(cpName, lines);
    if (built.error) {
      setError(built.error);
      return;
    }
    setLoading(true);
    try {
      const json = await api<UploadResult>("/api/v1/uploads/rows", {
        method: "POST",
        body: JSON.stringify({
          upload_type: uploadType,
          period_year: year,
          period_month: month,
          stock_date: stockDate || null,
          rows: built.rows,
        }),
      });
      onSuccess(json);
      setLines([newManualLine()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="panel upload-form" onSubmit={onSubmit}>
      {error && <div className="alert">{error}</div>}
      <div className="grid-4">
        <CounterpartySelect
          value={cpId || cpName}
          onChange={setCpId}
          onSelect={onPickCounterparty}
          onCreateName={(name) => {
            setCpId("");
            setCpName(name);
            setShops([]);
          }}
          allowEmpty
          allowCreate
          compact
        />
        <label className="field">
          <span>Тип</span>
          <Select value={uploadType} onChange={setUploadType} options={TYPE_OPTIONS} />
        </label>
        <label className="field">
          <span>Год</span>
          <Select value={String(year)} onChange={(v) => setYear(Number(v))} options={yearOptions()} />
        </label>
        <label className="field">
          <span>Месяц</span>
          <Select value={String(month)} onChange={(v) => setMonth(Number(v))} options={MONTH_OPTIONS} />
        </label>
      </div>
      {(stockRequired || uploadType === "promo_motivation") && (
        <label className="field">
          <span>{stockRequired ? "Дата остатков" : "Дата остатков"}</span>
          <DatePicker
            value={stockDate}
            onChange={setStockDate}
            placeholder={stockRequired ? "Выберите дату" : "Необязательно"}
          />
        </label>
      )}
      <div className={`manual-grid ${showPrice ? "has-price" : ""}`}>
        <div className="manual-grid-row heads">
          <div className="manual-grid-head">Артикул</div>
          <div className="manual-grid-head">Магазин</div>
          <div className="manual-grid-head">Кол-во</div>
          {showPrice && <div className="manual-grid-head">Цена</div>}
          <div className="manual-grid-head" />
        </div>
        {lines.map((line) => (
          <div key={line.key} className="manual-grid-row">
            <ArticleSelect value={line.article} onChange={(article) => updateLine(line.key, { article })} />
            <Select
              value={line.shop}
              onChange={(shop) => updateLine(line.key, { shop })}
              options={shopOptions}
              placeholder="Магазин"
              search={shops.length ? undefined : line.shop}
              onSearch={shops.length ? undefined : (shop) => updateLine(line.key, { shop })}
              searchPlaceholder="Магазин"
              allowCreate={!shops.length}
            />
            <NumberField
              value={line.quantity}
              onChange={(quantity) => updateLine(line.key, { quantity })}
              min={1}
              integer
            />
            {showPrice && (
              <NumberField
                value={line.price}
                onChange={(price) => updateLine(line.key, { price })}
                min={0}
                step={1000}
                placeholder="—"
              />
            )}
            <button
              type="button"
              className="btn secondary sm"
              disabled={lines.length === 1}
              onClick={() => setLines((prev) => prev.filter((item) => item.key !== line.key))}
            >
              Удалить
            </button>
          </div>
        ))}
      </div>
      <div className="upload-form-actions" style={{ justifyContent: "space-between" }}>
        <button type="button" className="btn secondary" onClick={() => setLines((prev) => [...prev, newManualLine()])}>
          Добавить строку
        </button>
        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Сохраняем…" : "Сохранить"}
        </button>
      </div>
    </form>
  );
}
