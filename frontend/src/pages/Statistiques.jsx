// Statistiques d'examens : taux de réussite par épreuve, type, catégorie et mois ; tentatives moyennes ; délai moyen jusqu'au permis.
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Texte } from "../composants/Champs.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { trierLignes, useTri } from "../lib/tri.js";

function Carte({ titre, valeur, detail }) {
  return <div className="rounded-2xl bg-white p-4 ring-1 ring-encre/5"><p className="text-xs font-semibold text-ardoise">{titre}</p><p className="mt-1 text-2xl font-extrabold tabular-nums text-emeraude">{valeur ?? "—"}</p>{detail && <p className="text-xs text-slate-500">{detail}</p>}</div>;
}

/** Tableau d'un regroupement : passés, admis, absents (nombres à droite) et taux avec barre (jamais la couleur seule : le pourcentage est écrit). */
function Groupe({ titre, lignes, libelle }) {
  const tri = useTri();
  const l = trierLignes(lignes, tri.cle, tri.sens);
  return (
    <section className="rounded-2xl bg-white p-4 ring-1 ring-encre/5"><h2 className="font-semibold">{titre}</h2>
      <table className="tableau mt-2"><thead><tr><ThTri cle="cle" tri={tri}>{libelle}</ThTri><ThTri cle="passes" tri={tri} numerique>Présents</ThTri><ThTri cle="admis" tri={tri} numerique>Admis</ThTri><ThTri cle="absents" tri={tri} numerique>Absents</ThTri><ThTri cle="taux" tri={tri} numerique>Réussite</ThTri></tr></thead>
        <tbody>{l.map((g) => <tr key={g.cle}><td className="font-semibold text-emeraude">{g.cle}</td><td className="num">{g.passes}</td><td className="num text-emerald-700">{g.admis}</td><td className="num">{g.absents}</td><td className="num font-semibold">{g.taux === null ? "—" : `${g.taux} %`}</td></tr>)}
          {!l.length && <tr><td colSpan={5} className="text-slate-500">Aucune donnée.</td></tr>}</tbody>
        <tfoot><tr className="font-bold bg-brume"><td>{l.length} ligne(s)</td><td className="num">{l.reduce((a, g) => a + g.passes, 0)}</td><td className="num">{l.reduce((a, g) => a + g.admis, 0)}</td><td className="num">{l.reduce((a, g) => a + g.absents, 0)}</td><td /></tr></tfoot></table>
    </section>
  );
}

export default function Statistiques() {
  const { avecToast } = useApp();
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [d, setD] = useState(null);
  const charger = useCallback(() => api(`/statistiques/examens?du=${du}&au=${au}`).then(setD), [du, au]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Statistiques d'examens</h1><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des statistiques", charger, () => "Statistiques actualisées")}>Actualiser</Bouton></div>
      <div className="mt-3 grid gap-x-3 sm:grid-cols-4"><Texte libelle="Du (12 derniers mois par défaut)" type="date" valeur={du} onChange={setDu} /><Texte libelle="Au" type="date" valeur={au} onChange={setAu} /></div>
      {!d ? <div className="py-10 flex justify-center"><span className="jauge" /></div> : <>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Carte titre="Taux de réussite global" valeur={d.taux_global === null ? null : `${d.taux_global} %`} detail={`${d.admis} admis sur ${d.passes} présents`} />
          <Carte titre="Permis obtenus" valeur={d.permis_obtenus} detail="sur la période" />
          <Carte titre="Tentatives pour réussir" valeur={d.tentatives_moyennes_pour_reussir} detail="en moyenne" />
          <Carte titre="Délai jusqu'au permis" valeur={d.delai_moyen_permis_jours === null ? null : `${d.delai_moyen_permis_jours} j`} detail="de l'inscription au permis" />
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2"><Groupe titre="Par épreuve" libelle="Épreuve" lignes={d.par_epreuve} /><Groupe titre="Par type d'examen" libelle="Type" lignes={d.par_type} />
          <Groupe titre="Par catégorie de permis" libelle="Catégorie" lignes={d.par_categorie} /><Groupe titre="Par mois" libelle="Mois" lignes={d.par_mois} /></div></>}
    </div>
  );
}
