import { useEffect, useState } from "react";
import { type DateRange, readStoredPeriod, writeStoredPeriod } from "./storedPeriod";

export function useStoredPeriod(key: string, fallback: DateRange) {
  const [from, setFrom] = useState(() => readStoredPeriod(key, fallback).from);
  const [to, setTo] = useState(() => readStoredPeriod(key, fallback).to);

  useEffect(() => {
    writeStoredPeriod(key, { from, to });
  }, [key, from, to]);

  function setPeriod(nextFrom: string, nextTo: string) {
    setFrom(nextFrom);
    setTo(nextTo);
  }

  return { from, to, setFrom, setTo, setPeriod };
}
