import Select from "./Select";
import { useODataSources, type ODataSourceOption } from "../odataSources";

type Props = {
  value: string;
  onChange: (value: string) => void;
  sources?: ODataSourceOption[];
  emptyLabel?: string;
  includeEmpty?: boolean;
};

export default function SourceSelect({
  value,
  onChange,
  sources: preset,
  emptyLabel = "Все",
  includeEmpty = true,
}: Props) {
  const { sources } = useODataSources(preset);
  const options = [
    ...(includeEmpty ? [{ value: "", label: emptyLabel }] : []),
    ...sources.map((s) => ({ value: s.source_id, label: s.label || s.source_id })),
  ];
  return <Select value={value} onChange={onChange} options={options} placeholder="База" />;
}
