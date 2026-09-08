type Props = { rows?: number; cols?: number };

export default function TableSkeleton({ rows = 6, cols = 5 }: Props) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <tbody>
          {Array.from({ length: rows }).map((_, row) => (
            <tr key={row} className="table-skeleton-row">
              {Array.from({ length: cols }).map((_, col) => (
                <td key={col}>
                  <span className="skel" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
