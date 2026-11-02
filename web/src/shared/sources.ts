export interface GeneralSource {
  id: "openrn" | "litfl";
  idPrefix: string;
  name: string;
  publisher: string;
  works: string;
  licence: string;
  licenceUrl: string;
  homeUrl: string;
  commercialUse: boolean;
}

export const GENERAL_SOURCES: GeneralSource[] = [
  {
    id: "openrn",
    idPrefix: "OPENRN_",
    name: "Open RN",
    publisher: "Open Resources for Nursing (Open RN), WisTech Open, edited by Kimberly Ernstmeyer and Elizabeth Christman",
    works: "Health Alterations; Nursing Advanced Skills, chapter 7 (ECGs)",
    licence: "CC BY 4.0",
    licenceUrl: "https://creativecommons.org/licenses/by/4.0/",
    homeUrl: "https://wtcs.pressbooks.pub/healthalts/",
    commercialUse: true,
  },
  {
    id: "litfl",
    idPrefix: "LITFL_",
    name: "LITFL ECG Library",
    publisher: "Life in the Fast Lane (LITFL), Dr Ed Burns, Dr Robert Buttner and contributors",
    works: "ECG Library",
    licence: "CC BY-NC-SA 4.0",
    licenceUrl: "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    homeUrl: "https://litfl.com/ecg-library/",
    commercialUse: false,
  },
];

export const GENERAL_QUESTION_LICENCE = { name: "CC BY-NC-SA 4.0", url: "https://creativecommons.org/licenses/by-nc-sa/4.0/" };

export function generalSourceFor(documentId: string): GeneralSource | null {
  return GENERAL_SOURCES.find((s) => documentId.startsWith(s.idPrefix)) ?? null;
}
