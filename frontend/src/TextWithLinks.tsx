export default function TextWithLinks({ text }: { text: string }) {
  return (
    <>
      {text.split(/(https?:\/\/[^\s<>"{}()]+)/g).map((part, index) => {
        if (!/^https?:\/\//.test(part)) return part;
        const target = part.replace(/[.,;!?]+$/, "");
        try {
          const url = new URL(target);
          if (url.username || url.password) return part;
          return (
            <a
              key={index}
              href={url.href}
              target="_blank"
              rel="noreferrer noopener"
            >
              {part}
            </a>
          );
        } catch {
          return part;
        }
      })}
    </>
  );
}
