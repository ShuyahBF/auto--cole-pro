// Examens internes et externes : liste des sessions (à venir par défaut), planning du mois, création, détail en FENÊTRE MODALE
// (inscription avec éligibilité annoncée, convocations et liste de présence PDF, saisie des résultats). Totaux sous le tableau (règle 25).
import { CalendarDays, ClipboardCheck, FileText, Plus, RefreshCw, Save, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import PdfInterne from "../composants/PdfInterne.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { aujourdhui, dateFr } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

const TYPES = [{ valeur: "interne", libelle: "Examen interne (blanc)" }, { valeur: "externe", libelle: "Examen externe (officiel)" }];
const RES = { inscrit: ["Inscrit", "gris"], admis: ["Admis", "vert"], ajourne: ["Ajourné", "rouge"], absent: ["Absent", "orange"], retire: ["Retiré", "gris"] };

function NouvelleSession({ onFermer, onFait }) {
  const { parametres, avecToast } = useApp();
  const f = useFormulaire({ type: "interne", epreuve: "", categorie: "", date: aujourdhui(), heure: "08:00", lieu: "", capacite: 20, organisme: "", examinateur: "" });
  const v = f.valeurs;
  const enregistrer = () => avecToast("Création de la session", () => api("/examens/sessions", { methode: "POST", corps: v }), () => "Session planifiée").then(onFait).catch(() => {});
  return (
    <Modal titre="Planifier une session d'examen" onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!v.epreuve || !v.categorie || !v.lieu} onClick={enregistrer}>Planifier</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Liste libelle="Type d'examen *" valeur={v.type} onChange={(x) => f.maj("type", x)} vide={null} options={TYPES} />
      <div className="grid grid-cols-2 gap-x-3">
        <Liste libelle="Épreuve *" valeur={v.epreuve} onChange={(x) => f.maj("epreuve", x)} options={(parametres?.epreuves || []).map((e) => ({ valeur: e.code, libelle: e.libelle }))} />
        <Liste libelle="Catégorie *" valeur={v.categorie} onChange={(x) => f.maj("categorie", x)} options={(parametres?.categories || []).map((c) => c.code)} />
        <Texte libelle="Date *" type="date" valeur={v.date} onChange={(x) => f.maj("date", x)} /><Texte libelle="Heure" type="time" valeur={v.heure} onChange={(x) => f.maj("heure", x)} />
        <Texte libelle="Capacité" type="number" valeur={v.capacite} onChange={(x) => f.maj("capacite", x)} min="1" /><Texte libelle="Examinateur" valeur={v.examinateur} onChange={(x) => f.maj("examinateur", x)} />
      </div>
      <Texte libelle="Lieu *" valeur={v.lieu} onChange={(x) => f.maj("lieu", x)} placeholder="Centre d'examen, circuit…" /><Texte libelle="Organisme / centre d'examen" valeur={v.organisme} onChange={(x) => f.maj("organisme", x)} />
    </Modal>
  );
}

function Detail({ id, onFermer, onChange }) {
  const { avecToast, toast, utilisateur } = useApp();
  const [s, setS] = useState(null);
  const [pdf, setPdf] = useState(null);
  const [recherche, setRecherche] = useState("");
  const [eligibles, setEligibles] = useState(null);
  const [res, setRes] = useState({});                      // inscription_id → statut choisi
  const peutEcrire = ["super_admin", "directeur", "gestionnaire", "secretaire"].includes(utilisateur.role);
  const charger = useCallback(() => api(`/examens/sessions/${id}`).then((x) => { setS(x); setRes({}); }), [id]);
  useEffect(() => { charger().catch((e) => toast(e.message, "erreur")); }, [charger, toast]);
  if (!s) return <Modal titre="Session d'examen" onFermer={onFermer}><div className="py-8 flex justify-center"><span className="jauge" /></div></Modal>;
  const inscrire = (e, forcer = false) => avecToast("Inscription", () => api(`/examens/sessions/${id}/inscriptions`, { methode: "POST", corps: { eleve_id: e.id, forcer } }), () => `${e.nom} inscrit(e)`)
    .then(() => { charger(); onChange(); setEligibles(null); }).catch(() => {});
  const retirer = (i) => avecToast("Retrait", () => api(`/examens/inscriptions/${i.id}/retirer`, { methode: "POST", corps: {} }), () => "Inscrit retiré").then(() => { charger(); onChange(); }).catch(() => {});
  const enregistrer = (cloturer) => avecToast("Enregistrement des résultats", () => api(`/examens/sessions/${id}/resultats`, { methode: "POST", corps: { cloturer, resultats: Object.entries(res).map(([inscription_id, statut]) => ({ inscription_id, statut })) } }),
    (r) => `Résultats enregistrés${r.nouveaux_diplomes ? ` · ${r.nouveaux_diplomes} nouveau(x) permis` : ""}`).then(() => { charger(); onChange(); }).catch(() => {});
  const ouvert = s.statut === "planifiee";
  return (
    <>
      <Modal titre={`${s.epreuve_libelle} — ${s.categorie}`} large onFermer={onFermer} pied={<><Bouton icone={FileText} petit onClick={() => setPdf({ t: "Liste de présence", c: `/examens/sessions/${id}/presence` })}>Liste de présence</Bouton><Bouton onClick={onFermer}>Fermer</Bouton></>}>
        <div className="flex flex-wrap items-center gap-2 text-sm"><Pastille couleur={s.type === "externe" ? "violet" : "bleu"}>{s.type_libelle}</Pastille><Pastille couleur={ouvert ? "vert" : "gris"}>{s.statut_libelle}</Pastille>
          <span>{dateFr(s.date)} {s.heure} · {s.lieu}</span></div>
        <p className="mt-1 text-sm text-ardoise">{s.inscrits} inscrit(s) sur {s.capacite} · {s.places_restantes} place(s) libre(s){s.examinateur && ` · examinateur : ${s.examinateur}`}</p>
        <table className="tableau mt-3"><thead><tr><th>Candidat</th><th>Tentative</th><th>Résultat</th><th /></tr></thead>
          <tbody>{s.inscriptions.filter((i) => i.statut !== "retire").map((i) => (
            <tr key={i.id}><td><span className="font-semibold">{i.eleve_nom}</span><div className="text-xs text-slate-500">{i.matricule}</div></td><td className="num">{i.tentative}</td>
              <td>{i.statut === "inscrit" && peutEcrire && s.statut !== "annulee" ? <select className="rounded border border-slate-300 px-2 py-1 text-sm" value={res[i.id] || ""} onChange={(e) => setRes({ ...res, [i.id]: e.target.value })}>
                <option value="">— À saisir —</option><option value="admis">Admis</option><option value="ajourne">Ajourné</option><option value="absent">Absent</option></select> : <Pastille couleur={RES[i.statut][1]}>{RES[i.statut][0]}</Pastille>}</td>
              <td className="whitespace-nowrap"><BoutonIcone icone={FileText} libelle="Convocation" onClick={() => setPdf({ t: "Convocation", c: `/examens/inscriptions/${i.id}/convocation` })} />
                {i.statut === "inscrit" && peutEcrire && ouvert && <button className="ml-1 text-xs text-rose-700 underline" onClick={() => retirer(i)}>Retirer</button>}</td></tr>))}
            {!s.inscriptions.length && <tr><td colSpan={4} className="text-slate-500">Aucun inscrit.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{s.inscrits} candidat(s)</td><td /><td colSpan={2}>{s.admis} admis · {s.ajournes} ajourné(s) · {s.absents} absent(s)</td></tr></tfoot></table>
        {peutEcrire && s.statut !== "annulee" && Object.values(res).some(Boolean) && <div className="mt-3 flex flex-wrap gap-2"><Bouton icone={Save} variante="principal" petit onClick={() => enregistrer(false)}>Enregistrer les résultats</Bouton>
          <Bouton icone={ClipboardCheck} variante="vert" petit onClick={() => enregistrer(true)}>Enregistrer et clôturer</Bouton></div>}
        {peutEcrire && ouvert && s.places_restantes > 0 && (
          <div className="mt-4 rounded-2xl bg-brume p-3"><p className="mb-1 text-sm font-semibold">Inscrire un élève</p>
            <div className="flex gap-2"><input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Nom ou matricule" className="w-full rounded-lg border border-slate-300 px-3 py-2" />
              <Bouton icone={UserPlus} petit onClick={() => api(`/examens/sessions/${id}/eligibles?q=${encodeURIComponent(recherche)}`).then(setEligibles).catch((e) => toast(e.message, "erreur"))}>Chercher</Bouton></div>
            {eligibles && <ul className="mt-2 space-y-1 text-sm">{eligibles.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-2 rounded-lg bg-white p-2"><span><b>{e.nom}</b> <span className="text-xs text-slate-500">{e.matricule}</span>
                {e.motifs.length > 0 && <span className="block text-xs text-rose-700">{e.motifs.join(" ; ")}</span>}</span>
                {e.motifs.length === 0 ? <Bouton petit variante="vert" onClick={() => inscrire(e)}>Inscrire</Bouton> : ["super_admin", "directeur", "gestionnaire"].includes(utilisateur.role) && s.type === "interne" && e.motifs.every((m) => m.startsWith("Impayé")) ? <Bouton petit onClick={() => inscrire(e, true)}>Forcer</Bouton> : null}</li>))}
              {!eligibles.length && <li className="text-slate-500">Aucun élève trouvé.</li>}</ul>}</div>)}
      </Modal>
      {pdf && <PdfInterne titre={pdf.t} chemin={pdf.c} onFermer={() => setPdf(null)} />}
    </>
  );
}

export default function Examens() {
  const { utilisateur, avecToast } = useApp();
  const [liste, setListe] = useState(null);
  const [mode, setMode] = useState("a_venir");            // a_venir | passes | planning
  const [filtreType, setFiltreType] = useState("");
  const [mois, setMois] = useState(aujourdhui().slice(0, 7));
  const [plan, setPlan] = useState(null);
  const [nouveau, setNouveau] = useState(false);
  const [ouvert, setOuvert] = useState("");
  const tri = useTri();
  const peutEcrire = ["super_admin", "directeur", "gestionnaire", "secretaire"].includes(utilisateur.role);
  const charger = useCallback(() => {
    if (mode === "planning") return api(`/examens/planning?mois=${mois}`).then(setPlan);
    const q = mode === "passes" ? `du=2000-01-01&au=${aujourdhui()}` : "";
    return api(`/examens/sessions?type=${filtreType}&${q}`).then(setListe);
  }, [mode, mois, filtreType]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const lignes = liste ? trierLignes(liste, tri.cle, tri.sens) : [];
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Examens</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des examens", charger, () => "Examens actualisés")}>Actualiser</Bouton>
          {peutEcrire && <Bouton icone={Plus} variante="principal" petit onClick={() => setNouveau(true)}>Planifier une session</Bouton>}</div></div>
      <div className="mt-3 grid gap-x-3 sm:grid-cols-4">
        <Liste libelle="Affichage" valeur={mode} onChange={setMode} vide={null} options={[{ valeur: "a_venir", libelle: "Sessions à venir" }, { valeur: "passes", libelle: "Sessions passées" }, { valeur: "planning", libelle: "Planning du mois" }]} />
        {mode === "planning" ? <Texte libelle="Mois" type="month" valeur={mois} onChange={setMois} /> : <Liste libelle="Type" valeur={filtreType} onChange={setFiltreType} vide="Tous" options={TYPES} />}
      </div>
      {mode === "planning" ? (!plan ? <div className="py-10 flex justify-center"><span className="jauge" /></div> : (
        <div className="space-y-3">{plan.jours.map((j) => (
          <section key={j.date} className="rounded-2xl bg-white p-3 ring-1 ring-encre/5"><h2 className="flex items-center gap-2 text-sm font-semibold text-emeraude"><CalendarDays size={16} />{dateFr(j.date)}</h2>
            <ul className="mt-2 space-y-1.5 text-sm">{j.sessions.map((s) => (
              <li key={s.id}><button className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-sky-100/60" onClick={() => setOuvert(s.id)}>
                <span>{s.heure} · {s.epreuve_libelle} ({s.categorie}) · {s.lieu}</span><span className="flex gap-1"><Pastille couleur={s.type === "externe" ? "violet" : "bleu"}>{s.type === "externe" ? "Externe" : "Interne"}</Pastille><Pastille>{s.inscrits}/{s.capacite}</Pastille></span></button></li>))}</ul></section>))}
          {!plan.jours.length && <p className="text-sm text-slate-500">Aucune session ce mois-ci.</p>}</div>
      )) : !liste ? <div className="py-10 flex justify-center"><span className="jauge" /></div> : (
        <div className="rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto"><table className="tableau"><thead><tr><ThTri cle="date" tri={tri}>Date</ThTri><ThTri cle="heure" tri={tri}>Heure</ThTri><ThTri cle="type" tri={tri}>Type</ThTri><ThTri cle="epreuve_libelle" tri={tri}>Épreuve</ThTri><ThTri cle="categorie" tri={tri}>Permis</ThTri><ThTri cle="lieu" tri={tri}>Lieu</ThTri>
          <ThTri cle="inscrits" tri={tri} numerique>Inscrits</ThTri><ThTri cle="capacite" tri={tri} numerique>Capacité</ThTri><ThTri cle="admis" tri={tri} numerique>Admis</ThTri><th>État</th></tr></thead>
          <tbody>{lignes.map((s) => (
            <tr key={s.id} className={ouvert === s.id ? "ligne-selectionnee" : ""} onClick={() => setOuvert(s.id)} style={{ cursor: "pointer" }}><td className="font-semibold text-emeraude">{dateFr(s.date)}</td><td>{s.heure}</td><td><Pastille couleur={s.type === "externe" ? "violet" : "bleu"}>{s.type === "externe" ? "Externe" : "Interne"}</Pastille></td>
              <td>{s.epreuve_libelle}</td><td>{s.categorie}</td><td>{s.lieu}</td><td className="num">{s.inscrits}</td><td className="num">{s.capacite}</td><td className="num text-emerald-700">{s.admis}</td><td><Pastille couleur={s.statut === "planifiee" ? "vert" : "gris"}>{s.statut_libelle}</Pastille></td></tr>))}
            {!lignes.length && <tr><td colSpan={10} className="text-slate-500">Aucune session.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{lignes.length} session(s)</td><td colSpan={5} /><td className="num">{lignes.reduce((a, s) => a + s.inscrits, 0)}</td><td className="num">{lignes.reduce((a, s) => a + s.capacite, 0)}</td><td className="num">{lignes.reduce((a, s) => a + s.admis, 0)}</td><td /></tr></tfoot></table></div>)}
      {nouveau && <NouvelleSession onFermer={() => setNouveau(false)} onFait={() => { setNouveau(false); charger(); }} />}
      {ouvert && <Detail id={ouvert} onFermer={() => setOuvert("")} onChange={charger} />}
    </div>
  );
}
