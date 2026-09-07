export default function AngularGlowButton({
  href,
  children,
}: {
  href: string;
  children: string;
}) {
  return (
    <a className="angular-glow-btn" href={href}>
      {children}
    </a>
  );
}
