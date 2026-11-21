// Bandeau « Une nouvelle version d'AutoÉcole Pro est disponible » (même principe que SAWALI, ALBARKA et ShuyahStore).
// Toutes les 5 minutes, et quand la page redevient visible, la page d'accueil est téléchargée SANS cache et ses fichiers sont comparés à ceux de la page ouverte.
// S'ils diffèrent, une nouvelle version est en ligne : le bandeau propose « Actualiser » (pictogramme + légende) ou « Plus tard ».
// Vérification en arrière-plan : elle ne bloque jamais l'écran. Aucun effet en développement (fichiers sans empreinte).
import { Clock, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { empreinteChargee, empreinteHtml, nouvelleVersionDisponible } from "../lib/versionSite.js";

const INTERVALLE_MS = 5 * 60 * 1000;

export default function NouvelleVersionBandeau() {
  const [dispo, setDispo] = useState(false);
  const [masque, setMasque] = useState(false);
  const chargee = useRef("");
  useEffect(() => {
    let vivant = true;
    chargee.current = empreinteChargee(document);
    if (!chargee.current) return undefined;                          // développement : rien à surveiller
    const verifier = () => {
      if (document.hidden) return;
      fetch(`/?verif=${Date.now()}`, { cache: "no-store" }).then((r) => r.text())
        .then((html) => { if (vivant && nouvelleVersionDisponible(chargee.current, empreinteHtml(html))) setDispo(true); }).catch(() => {});
    };
    verifier();                                                      // une première vérification dès l'ouverture
    const id = setInterval(verifier, INTERVALLE_MS);
    document.addEventListener("visibilitychange", verifier);
    return () => { vivant = false; clearInterval(id); document.removeEventListener("visibilitychange", verifier); };
  }, []);
  if (!dispo || masque) return null;
  return (
    <div role="status" data-testid="bandeau-nouvelle-version" className="fixed bottom-4 left-1/2 z-[9999] flex max-w-[92vw] -translate-x-1/2 flex-wrap items-center gap-3 rounded-xl bg-encre px-4 py-3 text-sm text-white shadow-lg">
      <span>Une nouvelle version d'AutoÉcole Pro est disponible.</span>
      <button type="button" onClick={() => window.location.reload()} data-testid="bandeau-actualiser" className="inline-flex items-center gap-1 rounded-lg bg-citron px-3 py-1 font-semibold text-white">
        <RefreshCw size={16} aria-hidden="true" />Actualiser</button>
      <button type="button" onClick={() => setMasque(true)} className="inline-flex items-center gap-1 text-white/80 hover:text-white"><Clock size={16} aria-hidden="true" />Plus tard</button>
    </div>
  );
}
