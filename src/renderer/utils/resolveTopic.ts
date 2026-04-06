import { QUIZ_CATEGORIES } from "../data/quizCategories";

export function resolveTopic(categoryName: string): string | null {
  const normalised = categoryName.trim().toLowerCase();
  if (!normalised) return null;

  for (const cat of QUIZ_CATEGORIES) {
    const displayLower = cat.display.toLowerCase();
    const sectionLower = cat.section.toLowerCase();
    if (normalised === displayLower || normalised === sectionLower) {
      return cat.section;
    }
  }

  for (const cat of QUIZ_CATEGORIES) {
    const sectionLower = cat.section.toLowerCase();
    if (
      normalised.startsWith(sectionLower) ||
      sectionLower.startsWith(normalised)
    ) {
      return cat.section;
    }
  }

  return null;
}
