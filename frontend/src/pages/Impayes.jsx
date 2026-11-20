// Impayés : élèves avec un reste dû, retard d'échéancier en rouge (texte + couleur). Totaux sous le tableau (règle 25).
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Pastille } from "../composants/Champs.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { dateFr, montant } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

export default function Impayes() {
  const { parametres, avecToast, rafraichirCompteurs } = useApp();
  const [d, setD] = useState(null);
  const tri = useTri();
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => api("/impayes").then((r) => { setD(r); rafraichirCompteurs(); }), [rafraichirCompteurs]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  if (!d) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const lignes = trierLignes(d.impayes, tri.cle, tri.sens, { prochaine: (l) => l.prochaine_echeance?.date });
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Impayés</h1>
        <Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des impayés", charger, () => "Impayés actualisés")}>Actualiser</Bouton>
      </div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="matricule" tri={tri}>Matricule</ThTri><ThTri cle="nom" tri={tri}>Élève</ThTri><ThTri cle="telephone" tri={tri}>Téléphone</ThTri><ThTri cle="agence_nom" tri={tri}>Agence</ThTri>
          <ThTri cle="net_a_payer" tri={tri} numerique>À payer</ThTri><ThTri cle="paye" tri={tri} numerique>Payé</ThTri><ThTri cle="reste_du" tri={tri} numerique>Reste dû</ThTri><ThTri cle="retard" tri={tri} numerique>En retard</ThTri><ThTri cle="prochaine" tri={tri}>Prochaine échéance</ThTri></tr></thead>
          <tbody>{lignes.map((l) => (
            <tr key={l.id}><td className="font-semibold text-emeraude">{l.matricule}</td><td>{l.nom}</td><td>{l.telephone}</td><td>{l.agence_nom}</td><td className="num">{m(l.net_a_payer)}</td><td className="num text-emerald-700">{m(l.paye)}</td>
              <td className="num font-semibold">{m(l.reste_du)}</td><td className="num">{l.retard > 0 ? <Pastille couleur="rouge">{m(l.retard)} en retard</Pastille> : <span className="text-slate-400">—</span>}</td>
              <td>{l.prochaine_echeance ? `${dateFr(l.prochaine_echeance.date)} · ${m(l.prochaine_echeance.montant)}` : ""}</td></tr>))}
            {!lignes.length && <tr><td colSpan={9} className="text-slate-500">Aucun impayé : tous les élèves sont à jour.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{lignes.length} élève(s)</td><td colSpan={3} /><td /><td /><td className="num">{m(d.total_reste)}</td><td className="num">{m(d.total_retard)}</td><td /></tr></tfoot></table>
      </div>
    </div>
  );
}
