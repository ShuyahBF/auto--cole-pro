// Tableau de bord : chiffres clés de l'auto-école (bouton « Actualiser » avec toasts, règle 17).
import { GraduationCap, RefreshCw, TrendingUp, Wallet, AlertTriangle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { montant } from "../lib/format.js";

function Carte({ icone: Icone, titre, valeur, detail, couleur }) {
  return (
    <div className="rounded-2xl bg-white p-4 ring-1 ring-encre/5">
      <div className="flex items-center gap-2 text-xs font-semibold text-ardoise"><Icone size={16} className={couleur} />{titre}</div>
      <p className={`mt-2 text-2xl font-extrabold tabular-nums ${couleur}`}>{valeur}</p>
      {detail && <p className="mt-1 text-xs text-slate-500">{detail}</p>}
    </div>
  );
}

/** Variation en pourcentage entre ce mois et le précédent (texte + flèche : jamais la couleur seule). */
const variation = (a, b) => (!b ? "" : `${a >= b ? "▲" : "▼"} ${Math.abs(Math.round(((a - b) / b) * 100))} % vs mois précédent`);

export default function Tableau() {
  const { parametres, avecToast } = useApp();
  const [t, setT] = useState(null);
  const charger = useCallback(() => api("/tableau").then(setT), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  if (!t) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const m = (v) => montant(v, parametres?.devise, parametres?.decimales);
  const max = Math.max(1, ...t.par_categorie.map((c) => c.nombre));
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation du tableau de bord", charger, () => "Tableau de bord actualisé")}>Actualiser</Bouton>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Carte icone={GraduationCap} titre="Élèves" valeur={t.eleves_total} detail={`${t.inscriptions_mois} inscription(s) ce mois ${variation(t.inscriptions_mois, t.inscriptions_mois_precedent)}`} couleur="text-emeraude" />
        {t.encaisse_mois !== null && <Carte icone={Wallet} titre="Encaissé ce mois" valeur={m(t.encaisse_mois)} detail={`Aujourd'hui : ${m(t.encaisse_aujourdhui)} · ${variation(t.encaisse_mois, t.encaisse_mois_precedent)}`} couleur="text-emerald-700" />}
        {t.reste_du_total !== null && <Carte icone={AlertTriangle} titre="Reste à encaisser" valeur={m(t.reste_du_total)} detail={`${t.eleves_avec_impaye} élève(s) concerné(s)`} couleur="text-rose-700" />}
        <Carte icone={TrendingUp} titre="En formation" valeur={t.par_statut.find((s) => s.statut === "en_formation")?.nombre ?? 0} detail={`${t.par_statut.find((s) => s.statut === "pret_examen")?.nombre ?? 0} prêt(s) pour l'examen`} couleur="text-citron-600" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl bg-white p-4 ring-1 ring-encre/5">
          <h2 className="font-semibold">Élèves par statut</h2>
          <ul className="mt-3 space-y-1.5 text-sm">{t.par_statut.map((s) => <li key={s.statut} className="flex justify-between"><span>{s.libelle}</span><span className="font-semibold tabular-nums">{s.nombre}</span></li>)}</ul>
        </section>
        <section className="rounded-2xl bg-white p-4 ring-1 ring-encre/5">
          <h2 className="font-semibold">Élèves par catégorie de permis</h2>
          <ul className="mt-3 space-y-2 text-sm">{t.par_categorie.map((c) => (
            <li key={c.categorie} className="flex items-center gap-3"><span className="w-10 font-semibold text-emeraude">{c.categorie}</span>
              <span className="h-3 flex-1 overflow-hidden rounded-full bg-brume"><span className="block h-full rounded-full bg-emeraude" style={{ width: `${(c.nombre / max) * 100}%` }} /></span>
              <span className="w-8 text-right tabular-nums font-semibold">{c.nombre}</span></li>))}
            {!t.par_categorie.length && <li className="text-slate-500">Aucun élève pour le moment.</li>}</ul>
          {t.par_agence.length > 1 && <><h2 className="mt-5 font-semibold">Par agence</h2><ul className="mt-2 space-y-1 text-sm">{t.par_agence.map((a) => <li key={a.agence} className="flex justify-between"><span>{a.agence}</span><span className="font-semibold tabular-nums">{a.nombre}</span></li>)}</ul></>}
        </section>
      </div>
    </div>
  );
}
