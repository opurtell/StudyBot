import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { highlightRanges, SourcePanel } from "../../src/client/components/QuizParts";

const TEXT = "## Hypoglycaemia\nHypoglycaemia is a BGL below 4 mmol/L.\nGive oral glucose 15 g if able to swallow.\nRecheck BGL in 15 minutes.";

function panel(props: { sourceQuote?: string; answerQuotes?: string[] }) {
  return render(
    <MemoryRouter>
      <SourcePanel sourceText={TEXT} citation="ACTAS CMG 10" documentId="CMG_10_Diabetic" documentTitle="Diabetic Emergencies" {...props} />
    </MemoryRouter>,
  );
}

describe("highlightRanges", () => {
  it("prefers the AI's quote when it is in the source", () => {
    expect(highlightRanges(TEXT, "BGL below 4 mmol/L", ["Recheck BGL in 15 minutes."])).toEqual({ ranges: [[36, 54]], quoted: true });
  });

  it("falls back to the answer quotes, sorted and merged, skipping any not in the source", () => {
    const a = "Give oral glucose 15 g if able to swallow.";
    const b = "Hypoglycaemia is a BGL below 4 mmol/L.";
    const { ranges, quoted } = highlightRanges(TEXT, "a quote the model made up", [a, "missing line", b, "BGL below 4"]);
    expect(quoted).toBe(false);
    expect(ranges.map(([s, e]) => TEXT.slice(s, e))).toEqual([b, a]);
  });

  it("ignores a quote that is the whole source, as reveal used to send", () => {
    expect(highlightRanges(TEXT, TEXT, [])).toEqual({ ranges: [], quoted: false });
  });
});

describe("SourcePanel", () => {
  it("highlights the answer lines when revealing without AI marking", () => {
    const { container } = panel({ answerQuotes: ["Give oral glucose 15 g if able to swallow.", "Recheck BGL in 15 minutes."] });
    expect([...container.querySelectorAll("mark")].map((m) => m.textContent)).toEqual([
      "Give oral glucose 15 g if able to swallow.",
      "Recheck BGL in 15 minutes.",
    ]);
    expect(screen.getByText("Answer highlighted")).toBeInTheDocument();
    expect(screen.getByLabelText("Guideline extract")).toHaveTextContent(/Hypoglycaemia is a BGL below 4 mmol\/L\./);
  });

  it("renders the Markdown and highlights inside it", () => {
    const md = "[ACTAS CMG 10]\n#### Management\n\n- Give **oral glucose** 15 g.\n- Recheck BGL\n  in 15 minutes.\n- Call for backup.";
    const { container } = render(
      <MemoryRouter>
        <SourcePanel
          sourceText={md}
          answerQuotes={["- Give **oral glucose** 15 g.", "- Recheck BGL\n  in 15 minutes."]}
          citation="ACTAS CMG 10"
          documentId="CMG_10_Diabetic"
          documentTitle="Diabetic Emergencies"
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Management" })).toBeInTheDocument();
    expect(container.querySelector("strong")).toHaveTextContent("oral glucose");
    expect(container.textContent).not.toMatch(/\*\*|####/);
    const items = [...container.querySelectorAll("li")];
    expect(items).toHaveLength(3);
    expect([...items[0]!.querySelectorAll("mark")].map((m) => m.textContent).join("")).toBe("Give oral glucose 15 g.");
    expect([...items[1]!.querySelectorAll("mark")].map((m) => m.textContent).join("")).toBe("Recheck BGL\nin 15 minutes.");
    expect(items[2]!.querySelector("mark")).toBeNull();
  });

  it("shows the source plainly when there is nothing to highlight", () => {
    const { container } = panel({});
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.queryByText(/highlighted/)).not.toBeInTheDocument();
  });
});
