import { Link } from "react-router";

export function NotFound() {
  return (
    <section className="space-y-3">
      <h1 className="font-headline text-3xl font-semibold">Page not found</h1>
      <Link to="/" className="underline">
        Go home
      </Link>
    </section>
  );
}
