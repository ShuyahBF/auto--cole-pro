// Évaluations par les clients : synthèse (satisfaction, NPS, critères, moniteurs), liste des avis, réponse et publication (si le client l'a autorisée), lien de demande.
import { Copy, RefreshCw, Save, Star } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Liste, Pastille } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { dateFr } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

const Etoiles = ({ n }) => <span aria-label={`${n} sur 5`} className="whitespace-nowrap text-citron">{"★".repeat(n)}<span className="text-slate-300">{"★".repeat(5 - n)}</span> <span className="text-xs text-ardoise">{n}/5</span></span>;

function Carte({ titre, valeur, detail }) {
  return <div className="rounded-2xl bg-white p-4 ring-1 ring-encre/5"><p className="text-xs font-semibold text-ardoise">{titre}</p><p className="mt-1 text-2xl font-extrabold tabular-nums text-emeraude">{valeur ?? "—"}</p>{detail && <p className="text-xs text-slate-500">{detail}</p>}</div>;
}

function Detail({ avis, onFermer, onFait, peutGerer }) {
  const { avecToast } = useApp();
  const [rep, setRep] = useState(avis.reponse_ecole);
  const go = (corps, ok) => avecToast("Enregistrement", () => api(`/avis/${avis.id}`, { methode: "PUT", corps }), () => ok).then(onFait).catch(() => {});
  return (
    <Modal titre={`Avis de ${avis.prenom}`} onFermer={onFermer} pied={<>{peutGerer && <Bouton icone={Save} variante="principal" disabled={rep === avis.reponse_ecole} onClick={() => go({ reponse_ecole: rep }, "Réponse enregistrée")}>Enregistrer la réponse</Bouton>}<Bouton onClick={onFermer}>Fermer</Bouton></>}>
      <p className="text-sm"><Etoiles n={avis.note_globale} /> {avis.nps !== null && <span className="ml-2">Recommandation : <b>{avis.nps}/10</b></span>}</p>
      <ul className="mt-2 text-sm">{Object.entries(avis.notes).map(([k, v]) => <li key={k} className="flex justify-between"><span className="capitalize">{k}</span><Etoiles n={v} /></li>)}</ul>
      {/* Texte écrit par un client : affiché tel quel (échappé par React), jamais interprété */}
      {avis.commentaire && <blockquote className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-brume p-3 text-sm">{avis.commentaire}</blockquote>}
      {peutGerer && <><label className="mt-3 block text-xs font-semibold text-ardoise">Votre réponse (note interne, visible si l'avis est publié)</label><textarea value={rep} onChange={(e) => setRep(e.target.value)} rows={3} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        {rep !== avis.reponse_ecole && <span className="text-xs text-orange-700">modifié, non enregistré</span>}
        <div className="mt-2">{avis.autorise_publication ? <Bouton petit variante={avis.publie ? "neutre" : "vert"} onClick={() => go({ publie: !avis.publie }, avis.publie ? "Avis dépublié" : "Avis publié")}>{avis.publie ? "Retirer de la publication" : "Publier cet avis"}</Bouton> : <Pastille>Publication non autorisée par le client</Pastille>}</div></>}
    </Modal>
  );
}

export default function Avis() {
  const { avecToast, utilisateur, toast } = useApp();
  const [syn, setSyn] = useState(null);
  const [liste, setListe] = useState([]);
  const [filtre, setFiltre] = useState("5");
  const [ouvert, setOuvert] = useState(null);
  const [eleves, setEleves] = useState([]);
  const [eid, setEid] = useState("");
  const [lien, setLien] = useState("");
  const tri = useTri();
  const peutGerer = ["gestionnaire", "directeur", "super_admin"].includes(utilisateur.role);
  const charger = useCallback(() => Promise.all([api("/avis/synthese").then(setSyn), api(`/avis?note_max=${filtre}`).then(setListe)]), [filtre]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  useEffect(() => { if (peutGerer) api("/eleves?statut=&limite=200&tri=nom&sens=asc").then((r) => setEleves(r.eleves)).catch(() => {}); }, [peutGerer]);
  const demander = () => avecToast("Création du lien", () => api("/avis/demandes", { methode: "POST", corps: { eleve_id: eid } }), (r) => "Lien créé (valable " + r.valide_jours + " jours)").then((r) => setLien(r.lien)).catch(() => {});
  if (!syn) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const lignes = trierLignes(liste, tri.cle, tri.sens);
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Évaluations des clients</h1><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des avis", charger, () => `${syn.nombre} avis`)}>Actualiser</Bouton></div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Carte titre="Satisfaction moyenne" valeur={syn.satisfaction === null ? null : `${syn.satisfaction} / 5`} detail={`${syn.nombre} avis`} />
        <Carte titre="Net Promoter Score" valeur={syn.nps} detail={`${syn.promoteurs} promoteurs · ${syn.neutres} neutres · ${syn.detracteurs} détracteurs`} />
        <Carte titre="Taux de réponse" valeur={syn.taux_reponse === null ? null : `${syn.taux_reponse} %`} detail={`${syn.demandes} demande(s) envoyée(s)`} />
        <section className="rounded-2xl bg-white p-4 ring-1 ring-encre/5"><p className="text-xs font-semibold text-ardoise">Par critère</p><ul className="mt-1 space-y-0.5 text-xs">{syn.par_critere.map((c) => <li key={c.cle} className="flex justify-between"><span>{c.libelle}</span><b className="tabular-nums">{c.moyenne ?? "—"}</b></li>)}</ul></section>
      </div>
      {syn.par_moniteur.length > 0 && <section className="mt-3 rounded-2xl bg-white p-4 ring-1 ring-encre/5"><h2 className="font-semibold">Par moniteur</h2><table className="tableau mt-1"><thead><tr><th>Moniteur</th><th className="num">Avis</th><th className="num">Note moyenne</th></tr></thead>
        <tbody>{syn.par_moniteur.map((m) => <tr key={m.moniteur}><td className="font-semibold text-emeraude">{m.moniteur}</td><td className="num">{m.nombre}</td><td className="num font-bold">{m.moyenne} / 5</td></tr>)}</tbody></table></section>}
      {peutGerer && <section className="mt-3 rounded-2xl bg-brume p-3"><p className="text-sm font-semibold">Demander un avis à un élève</p>
        <div className="grid gap-x-3 sm:grid-cols-[1fr_auto] items-end"><Liste libelle="Élève" valeur={eid} onChange={(x) => { setEid(x); setLien(""); }} options={eleves.map((e) => ({ valeur: e.id, libelle: `${e.nom} ${e.prenom} (${e.matricule})` }))} /><div className="pb-3"><Bouton icone={Star} variante="orange" disabled={!eid} onClick={demander}>Créer le lien</Bouton></div></div>
        {lien && <div className="mt-1 flex items-center gap-2 text-sm"><code className="min-w-0 flex-1 truncate rounded bg-white px-2 py-1">{lien}</code><Bouton icone={Copy} petit onClick={() => navigator.clipboard?.writeText(lien).then(() => toast("Lien copié", "ok"))}>Copier</Bouton></div>}
        <p className="mt-1 text-xs text-ardoise">Pour les envois groupés (permis obtenus), utilisez le centre de messagerie.</p></section>}
      <div className="mt-4 flex items-end gap-3"><div className="w-56"><Liste libelle="Afficher" valeur={filtre} onChange={setFiltre} vide={null} options={[{ valeur: "5", libelle: "Tous les avis" }, { valeur: "3", libelle: "3 étoiles ou moins" }, { valeur: "2", libelle: "2 étoiles ou moins" }]} /></div></div>
      <div className="rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto"><table className="tableau"><thead><tr><ThTri cle="cree_le" tri={tri}>Date</ThTri><ThTri cle="prenom" tri={tri}>Élève</ThTri><ThTri cle="moniteur" tri={tri}>Moniteur</ThTri><ThTri cle="note_globale" tri={tri} numerique>Satisfaction</ThTri><ThTri cle="nps" tri={tri} numerique>Recommandation</ThTri><th>Commentaire</th><th>Publié</th></tr></thead>
        <tbody>{lignes.map((a) => <tr key={a.id} onClick={() => setOuvert(a)} style={{ cursor: "pointer" }}><td>{dateFr(a.cree_le)}</td><td className="font-semibold">{a.prenom}</td><td>{a.moniteur}</td><td className="num"><Etoiles n={a.note_globale} /></td><td className="num">{a.nps ?? ""}</td><td className="max-w-xs truncate">{a.commentaire}</td><td>{a.publie ? <Pastille couleur="vert">Publié</Pastille> : ""}</td></tr>)}
          {!lignes.length && <tr><td colSpan={7} className="text-slate-500">Aucun avis pour le moment.</td></tr>}</tbody>
        <tfoot><tr className="font-bold bg-brume"><td>{lignes.length} avis</td><td colSpan={2} /><td className="num">{syn.satisfaction ?? ""}</td><td colSpan={3} /></tr></tfoot></table></div>
      {ouvert && <Detail avis={ouvert} peutGerer={peutGerer} onFermer={() => setOuvert(null)} onFait={() => { setOuvert(null); charger(); }} />}
    </div>
  );
}
