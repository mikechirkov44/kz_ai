export type UploadErrorItem = {
  row: number;
  field: string;
  message: string;
  file_name?: string | null;
  counterparty?: string | null;
};

export function hasUploadErrors(errors?: UploadErrorItem[] | null): boolean {
  return Boolean(errors?.length);
}

export function uploadErrorSubtitle(processedRows: number, errors: UploadErrorItem[]): string {
  return `Обработано ${processedRows}, ошибок ${errors.length}`;
}
