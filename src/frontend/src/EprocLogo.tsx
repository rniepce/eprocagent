type Props = { size?: number };

export function EprocLogo({ size = 40 }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 120 120"
      width={size}
      height={size}
      role="img"
      aria-label="eproc"
    >
      <circle cx="42" cy="42" r="32" fill="#9bbce4" opacity="0.85" />
      <circle cx="50" cy="86" r="20" fill="#9bbce4" opacity="0.85" />
      <circle cx="76" cy="58" r="40" fill="#7eb0e0" opacity="0.95" />
      <text
        x="76"
        y="66"
        textAnchor="middle"
        fontFamily="'Helvetica Neue', Arial, sans-serif"
        fontSize="22"
        fontWeight="500"
        fill="#ffffff"
        letterSpacing="0.5"
      >
        eproc
      </text>
    </svg>
  );
}
