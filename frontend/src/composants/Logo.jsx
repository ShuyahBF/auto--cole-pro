// Logo AutoÉcole Pro : emblème rond blanc (volant bleu marine, repère orange) + nom « Auto » / « École Pro ».
export function Embleme({ taille = 44 }) {
  return (
    <svg viewBox="0 0 48 48" width={taille} height={taille} role="img" aria-label="AutoÉcole Pro" className="shrink-0 rounded-full bg-white">
      <circle cx="24" cy="24" r="14" fill="none" stroke="#03316E" strokeWidth="4" />
      <circle cx="24" cy="24" r="3.5" fill="#03316E" />
      <path d="M10 24h10M28 24h10M24 28v10" stroke="#03316E" strokeWidth="4" strokeLinecap="round" />
      <circle cx="24" cy="10" r="2.6" fill="#FF7A0A" />
    </svg>
  );
}

export default function Logo({ taille = 44, clair = false, nom = true }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Embleme taille={taille} />
      {nom && <span className={`font-display text-lg font-extrabold tracking-tight ${clair ? "text-white" : "text-emeraude"}`}>Auto<span className="text-citron">École Pro</span></span>}
    </span>
  );
}
