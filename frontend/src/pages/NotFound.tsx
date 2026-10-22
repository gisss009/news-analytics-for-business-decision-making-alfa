import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <section>
      <h1>Страница не найдена</h1>
      <p className="lead">
        <Link to="/">Вернуться на главный экран</Link>
      </p>
    </section>
  );
}
