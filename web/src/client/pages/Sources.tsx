import { Link } from "react-router";
import { GENERAL_QUESTION_LICENCE, GENERAL_SOURCES } from "../../shared/sources";

export function Sources() {
  return (
    <article className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Sources and licences</h1>
        <p className="text-on-surface-variant">Where every question comes from, in order of authority.</p>
      </header>

      <section className="space-y-2">
        <h2 className="font-headline text-xl font-semibold">1. ACTAS Clinical Management Guidelines</h2>
        <p>
          Guideline, clinical skill and medicine questions come from the ACT Ambulance Service Clinical Management
          Guidelines,{" "}
          <a className="underline" href="https://cmg.ambulance.act.gov.au" rel="noopener noreferrer" target="_blank">
            cmg.ambulance.act.gov.au
          </a>
          . They always take precedence over the general references below.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-headline text-xl font-semibold">2. General open references</h2>
        <p>
          Pathophysiology and ECG questions come from openly licensed references. They cover pathophysiology, physiology
          and ECG recognition only, never treatment, medicines or procedures. Each question is checked against the CMGs
          before it is used, and any question that conflicts with a CMG is left out.{" "}
          <Link to="/references" className="underline">
            Read the references
          </Link>
        </p>
        <ul className="space-y-3">
          {GENERAL_SOURCES.map((source) => (
            <li key={source.id} className="rounded-sm bg-surface-container-low p-4">
              <h3 className="font-semibold">
                <a className="underline" href={source.homeUrl} rel="noopener noreferrer" target="_blank">
                  {source.name}
                </a>
              </h3>
              <p className="text-sm">{source.works}</p>
              <p className="text-sm text-on-surface-variant">{source.publisher}</p>
              <p className="text-sm">
                Licence:{" "}
                <a className="underline" href={source.licenceUrl} rel="noopener noreferrer license" target="_blank">
                  {source.licence}
                </a>
              </p>
            </li>
          ))}
        </ul>
        <p className="text-sm">
          The source text has been adapted: treatment, medicine and procedure sections and all images were removed, the
          text was split into sections, and questions were written from it with AI and localised to Australian English.
          Neither publisher endorses this app. Each question shows the page it was adapted from.
        </p>
        <p className="text-sm">
          The pathophysiology and ECG questions and their adapted source text are shared under{" "}
          <a className="underline" href={GENERAL_QUESTION_LICENCE.url} rel="noopener noreferrer license" target="_blank">
            {GENERAL_QUESTION_LICENCE.name}
          </a>
          , as the LITFL licence requires. This app is free and non-commercial.
        </p>
      </section>
    </article>
  );
}
