import { useEffect } from "react";
import { APP_TITLE, formatPageTitle } from "./pageTitle";

export function usePageTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = formatPageTitle(title);
    return () => {
      document.title = previous || APP_TITLE;
    };
  }, [title]);
}
