// Journal d'audit : qui a fait quoi et quand (jamais de mot de passe ni de donnée sensible).
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { dateHeureFr } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

export default function Journal() {
  const { avecToast } = useApp();
  const [l, setL] = useState(null);
  const tri = useTri();
  const charger = useCallback(() => api("/journal?limite=300").then(setL), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  if (!l) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Journal d'audit</h1><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation du journal", charger, () => "Journal actualisé")}>Actualiser</Bouton></div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="quand" tri={tri}>Date et heure</ThTri><ThTri cle="acteur" tri={tri}>Compte</ThTri><ThTri cle="role" tri={tri}>Rôle</ThTri><ThTri cle="action" tri={tri}>Action</ThTri><ThTri cle="detail" tri={tri}>Détail</ThTri></tr></thead>
          <tbody>{trierLignes(l, tri.cle, tri.sens).map((j, i) => <tr key={i}><td className="whitespace-nowrap">{dateHeureFr(j.quand)}</td><td className="font-semibold text-emeraude">{j.acteur}</td><td>{j.role}</td><td>{j.action}</td><td>{j.detail}</td></tr>)}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{l.length} ligne(s)</td><td colSpan={4} /></tr></tfoot></table>
      </div>
    </div>
  );
}
