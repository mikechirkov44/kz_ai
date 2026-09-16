import RecText from "./RecText";
import { compactRecNumber, saleShareOfShip } from "../recommendations";

type Props = {
  clientAvg: number | null;
  shipmentAvg: number | null;
  gapPercent?: number | null;
};

export default function PriceGapMeter({ clientAvg, shipmentAvg, gapPercent }: Props) {
  const share = saleShareOfShip(clientAvg, shipmentAvg);
  if (share == null && clientAvg == null && shipmentAvg == null) return null;
  return (
    <div className="rec-gap">
      {share != null ? (
        <div className="rec-gap-track" aria-hidden="true">
          <i className="rec-gap-sale" style={{ width: `${share}%` }} />
        </div>
      ) : null}
      <div className="rec-gap-legend">
        {clientAvg != null ? (
          <span>
            продажа <RecText text={compactRecNumber(String(clientAvg))} />
          </span>
        ) : (
          <span />
        )}
        {shipmentAvg != null ? (
          <span>
            отгрузка <RecText text={compactRecNumber(String(shipmentAvg))} />
          </span>
        ) : null}
      </div>
      {gapPercent != null ? (
        <em className="rec-gap-delta">
          <RecText text={`−${gapPercent.toFixed(1)}%`} />
        </em>
      ) : null}
    </div>
  );
}
