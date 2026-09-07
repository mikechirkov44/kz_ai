import { splitRecNumbers } from "../recommendations";

export default function RecText({ text }: { text: string }) {
  return (
    <>
      {splitRecNumbers(text).map((part, idx) =>
        part.number ? (
          <strong key={idx} className="rec-num">
            {part.value}
          </strong>
        ) : (
          part.value
        ),
      )}
    </>
  );
}
