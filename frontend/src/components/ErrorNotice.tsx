interface ErrorNoticeProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

/** Says what went wrong and offers a way forward. */
export function ErrorNotice({ title, message, onRetry }: ErrorNoticeProps) {
  return (
    <div className="notice" role="alert">
      <h3>{title}</h3>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
