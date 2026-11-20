// Caisse et paiements : paiements d'une période (aujourd'hui par défaut), totaux par mode, reçu PDF dans le lecteur interne. Totaux collés sous le tableau (règle 25).
import { Eye, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Liste, Pastille, Texte } from "../composants/Champs.jsx";
import PdfInterne from "../composants/PdfInterne.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { aujourdhui, dateFr, montant } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

export default function Caisse() {
  const { parametres, avecToast } = useApp();
  const [du, setDu] = useState(aujourdhui());
  const [au, setAu] = useState(aujourdhui());
  const [mode, setMode] = useState("");
  const [d, setD] = useState(null);
  const [recu, setRecu] = useState("");
  const tri = useTri();
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => api(`/paiements?du=${du}&au=${au}&mode=${mode}`).then(setD), [du, au, mode]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const lignes = d ? trierLignes(d.paiements, tri.cle, tri.sens) : [];
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Caisse et paiements</h1>
        <Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation de la caisse", charger, () => "Caisse actualisée")}>Actualiser</Bouton>
      </div>
      <div className="mt-3 grid gap-x-3 sm:grid-cols-4">
        <Texte libelle="Du" type="date" valeur={du} onChange={setDu} /><Texte libelle="Au" type="date" valeur={au} onChange={setAu} />
        <Liste libelle="Mode de paiement" valeur={mode} onChange={setMode} vide="Tous" options={(parametres?.modes_paiement || []).map((x) => ({ valeur: x.cle, libelle: x.libelle }))} />
      </div>
      {d && <>
        <div className="mb-3 flex flex-wrap gap-2 text-sm">{Object.entries(d.par_mode).map(([k, v]) => <Pastille key={k} couleur="bleu">{k} : {m(v)}</Pastille>)}</div>
        <div className="rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
          <table className="tableau"><thead><tr><ThTri cle="recu" tri={tri}>Reçu</ThTri><ThTri cle="date" tri={tri}>Date</ThTri><ThTri cle="eleve_nom" tri={tri}>Élève</ThTri><ThTri cle="mode_libelle" tri={tri}>Mode</ThTri><ThTri cle="reference" tri={tri}>Référence</ThTri><ThTri cle="encaisse_par" tri={tri}>Caissier</ThTri><ThTri cle="montant" tri={tri} numerique>Montant</ThTri><th /></tr></thead>
            <tbody>{lignes.map((p) => (
              <tr key={p.id} className={p.annule ? "opacity-50 line-through" : ""}><td className="font-semibold text-emeraude">{p.recu}</td><td>{dateFr(p.date)}</td><td>{p.eleve_nom}<div className="text-xs text-slate-500">{p.matricule}</div></td><td>{p.mode_libelle}</td><td>{p.reference}</td><td>{p.encaisse_par}</td>
                <td className="num font-semibold text-emerald-700">{m(p.montant)}</td><td><BoutonIcone icone={Eye} libelle="Voir le reçu" onClick={() => setRecu(p.id)} /></td></tr>))}
              {!lignes.length && <tr><td colSpan={8} className="text-slate-500">Aucun paiement sur cette période.</td></tr>}</tbody>
            <tfoot><tr className="font-bold bg-brume"><td>{d.nombre} paiement(s)</td><td colSpan={5} /><td className="num">{m(d.total)}</td><td /></tr></tfoot></table>
        </div></>}
      {recu && <PdfInterne titre="Reçu de paiement" chemin={`/paiements/${recu}/recu`} onFermer={() => setRecu("")} />}
    </div>
  );
}
