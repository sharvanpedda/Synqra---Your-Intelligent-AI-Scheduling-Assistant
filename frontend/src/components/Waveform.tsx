/** Animated equalizer bars — used for listening / speaking states. */
export default function Waveform({
  bars = 9,
  active = true,
  color = "currentColor",
  className = "",
}: {
  bars?: number;
  active?: boolean;
  color?: string;
  className?: string;
}) {
  return (
    <span className={`flex h-4 items-center gap-[2px] ${className}`} aria-hidden>
      {Array.from({ length: bars }, (_, i) => (
        <span
          key={i}
          className="wave-bar w-[2.5px] rounded-full"
          style={{
            height: active ? `${8 + ((i * 5) % 7)}px` : "4px",
            background: color,
            opacity: active ? 1 : 0.35,
            animationDelay: `${(i % 8) * 0.1}s`,
          }}
        />
      ))}
    </span>
  );
}
