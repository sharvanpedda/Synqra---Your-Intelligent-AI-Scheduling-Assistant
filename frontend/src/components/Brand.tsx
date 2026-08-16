/** Brand lockup: logo mark + wordmark. size="lg" for prominent placements like the landing header. */
export default function Brand({ size = "default" }: { size?: "default" | "lg" }) {
  const lg = size === "lg";
  return (
    <span className="flex items-center gap-2.5 select-none">
      <img
        src="/logo-128.png"
        alt=""
        className={lg ? "h-11 w-11" : "h-7 w-7"}
        width={lg ? 44 : 28}
        height={lg ? 44 : 28}
      />
      <span
        className={`font-display font-semibold tracking-tight text-busy ${
          lg ? "text-2xl" : "text-sm"
        }`}
      >
        Syn<span className="text-signal">qra</span>
      </span>
    </span>
  );
}
