interface QuizQuestionProps {
  questionNumber: number;
  text: string;
  category: string;
}

export default function QuizQuestion({ questionNumber, text, category }: QuizQuestionProps) {
  return (
    <div className="text-center space-y-6">
      <span className="inline-block bg-tertiary-fixed/40 px-3 py-1 font-label text-[10px] uppercase tracking-widest text-on-surface-variant">
        Question {questionNumber}
      </span>
      <h1 className="font-headline text-display-sm text-primary leading-tight max-w-3xl mx-auto">
        {text}
      </h1>
      <span className="font-label text-label-sm text-on-surface-variant">
        {category}
      </span>
    </div>
  );
}
