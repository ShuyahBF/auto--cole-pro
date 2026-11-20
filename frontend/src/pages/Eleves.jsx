// Élèves : liste paginée (recherche, filtres, tri SERVEUR sur toutes les lignes), inscription et dossier de l'élève en FENÊTRES MODALES (règle 20),
// pièces reçues, échéancier, statut de formation et encaissement. Totaux collés sous la liste (règle 25).
import { BadgeCheck, CreditCard, Eye, Plus, RefreshCw, Save, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Case, Champ, Liste, Pastille, Texte, classeChamp } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import PdfInterne from "../composants/PdfInterne.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { aujourdhui, dateFr, montant } from "../lib/format.js";
import { useTri } from "../lib/tri.js";

const STATUTS = { inscrit: ["Inscrit", "gris"], en_formation: ["En formation", "bleu"], pret_examen: ["Prêt pour l'examen", "orange"], diplome: ["Permis obtenu", "vert"], abandon: ["Abandon", "rouge"], transfere: ["Transféré", "violet"] };
const SERVEUR = { matricule: "matricule", nom: "nom", date: "date", statut: "statut", categorie: "categorie", net: "net" };   // colonnes triables côté serveur

/** Fenêtre d'inscription d'un nouvel élève (tarif, promotion, agence, pièces déjà reçues). */
function Inscription({ onFermer, onFait }) {
  const { parametres, utilisateur, toast } = useApp();
  const f = useFormulaire({ nom: "", prenom: "", sexe: "", date_naissance: "", telephone: "", email: "", adresse: "", categorie: "", tarif_id: "", promotion: "", agence_id: "", pieces: {}, confirmer_doublon: false });
  const [tarifs, setTarifs] = useState([]);
  const [agences, setAgences] = useState([]);
  const [promos, setPromos] = useState([]);
  const [doublon, setDoublon] = useState(false);
  const [attente, setAttente] = useState(false);
  useEffect(() => { api("/tarifs").then(setTarifs); api("/agences").then(setAgences); api("/promotions").then(setPromos).catch(() => {}); }, []);
  const v = f.valeurs;
  const tarifsCat = tarifs.filter((t) => t.actif && t.categorie === v.categorie);
  const tarif = tarifs.find((t) => t.id === v.tarif_id);
  async function enregistrer() {
    setAttente(true);
    try {
      const r = await api("/eleves", { methode: "POST", corps: { ...v, confirmer_doublon: v.confirmer_doublon } });
      toast(`Élève inscrit : ${r.matricule}`, "ok");
      onFait(r);
    } catch (e) {
      if (e.statut === 409 && /existe déjà/.test(e.message)) setDoublon(true); else toast(e.message, "erreur");
    } finally { setAttente(false); }
  }
  return (
    <Modal titre="Inscrire un élève" large onFermer={onFermer} pied={<>
      <Bouton icone={Save} variante="principal" attente={attente} onClick={enregistrer}>Enregistrer l'inscription</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      {doublon && <div className="mb-3 rounded-xl bg-orange-50 p-3 text-sm text-orange-900 ring-1 ring-orange-200">Un élève de même nom, prénom et date de naissance existe déjà.
        <Case libelle="Je confirme : c'est bien une autre personne" valeur={v.confirmer_doublon} onChange={(x) => f.maj("confirmer_doublon", x)} /></div>}
      <div className="grid gap-x-3 sm:grid-cols-2">
        <Texte libelle="Nom *" valeur={v.nom} onChange={(x) => f.maj("nom", x)} placeholder="BADINI" />
        <Texte libelle="Prénom(s) *" valeur={v.prenom} onChange={(x) => f.maj("prenom", x)} placeholder="Awa" />
        <Texte libelle="Date de naissance *" type="date" valeur={v.date_naissance} onChange={(x) => f.maj("date_naissance", x)} max={aujourdhui()} />
        <Liste libelle="Sexe" valeur={v.sexe} onChange={(x) => f.maj("sexe", x)} options={[{ valeur: "F", libelle: "Féminin" }, { valeur: "M", libelle: "Masculin" }]} vide="—" />
        <Texte libelle="Téléphone *" valeur={v.telephone} onChange={(x) => f.maj("telephone", x)} placeholder={`+${parametres?.indicatif || "226"} 70 00 00 00`} />
        <Texte libelle="E-mail" type="email" valeur={v.email} onChange={(x) => f.maj("email", x)} placeholder="awa.badini@gmail.com" />
        <Texte libelle="Adresse" valeur={v.adresse} onChange={(x) => f.maj("adresse", x)} />
        <Liste libelle="Agence" valeur={v.agence_id} onChange={(x) => f.maj("agence_id", x)} options={agences.filter((a) => a.actif).map((a) => ({ valeur: a.id, libelle: a.nom }))} vide={agences.length > 1 ? "Agence principale" : null} />
        <Liste libelle="Catégorie de permis *" valeur={v.categorie} onChange={(x) => f.setValeurs((s) => ({ ...s, categorie: x, tarif_id: "" }))} options={(parametres?.categories || []).map((c) => ({ valeur: c.code, libelle: `${c.code} — ${c.libelle}` }))} />
        <Liste libelle="Forfait *" valeur={v.tarif_id} onChange={(x) => f.maj("tarif_id", x)} options={tarifsCat.map((t) => ({ valeur: t.id, libelle: `${t.libelle} (${montant(t.prix, parametres?.devise, parametres?.decimales)})` }))} vide={v.categorie ? "— Choisir —" : "Choisissez d'abord la catégorie"} />
        <Liste libelle="Promotion" valeur={v.promotion} onChange={(x) => f.maj("promotion", x)} options={promos.filter((p) => p.etat === "en_cours").map((p) => ({ valeur: p.code, libelle: `${p.libelle} (${p.type === "pourcentage" ? p.valeur + " %" : montant(p.valeur, parametres?.devise, parametres?.decimales)})` }))} vide="Aucune" />
      </div>
      {tarif && <p className="mb-3 text-sm text-ardoise">{tarif.heures_conduite} h de conduite · {tarif.seances_code} séances de code</p>}
      <p className="mb-1 text-xs font-semibold text-ardoise">Pièces déjà reçues</p>
      {(parametres?.pieces || []).map((p) => <Case key={p.cle} libelle={`${p.libelle}${p.obligatoire ? " *" : ""}`} valeur={v.pieces[p.cle]} onChange={(x) => f.maj("pieces", { ...v.pieces, [p.cle]: x })} />)}
      {utilisateur && null}
    </Modal>
  );
}

/** Livret de progression : heures effectuées / prévues, séances récentes, ajout d'une séance (moniteur et personnel), parcours d'examens. */
function Livret({ id, statut }) {
  const { avecToast, utilisateur } = useApp();
  const [l, setL] = useState(null);
  const [ex, setEx] = useState([]);
  const [n, setN] = useState({ type: "conduite", duree_min: 60, theme: "", appreciation: "" });
  const charger = useCallback(() => { api(`/eleves/${id}/seances`).then(setL).catch(() => {}); api(`/eleves/${id}/examens`).then(setEx).catch(() => {}); }, [id]);
  useEffect(() => { charger(); }, [charger]);
  if (!l) return null;
  const peut = ["moniteur", "secretaire", "gestionnaire", "directeur", "super_admin"].includes(utilisateur.role) && !["abandon", "transfere", "diplome"].includes(statut);
  const pct = l.heures_prevues ? Math.min(100, Math.round((l.heures_conduite / l.heures_prevues) * 100)) : 0;
  const ajouter = () => avecToast("Enregistrement de la séance", () => api(`/eleves/${id}/seances`, { methode: "POST", corps: n }), () => "Séance enregistrée").then(() => { setN({ ...n, theme: "" }); charger(); }).catch(() => {});
  return (
    <section className="mt-4"><h3 className="text-sm font-semibold">Livret de progression</h3>
      <p className="mt-1 text-sm">Conduite : <b>{l.heures_conduite} h</b> sur {l.heures_prevues} h prévues · Code : <b>{l.seances_code}</b> sur {l.seances_code_prevues} séances</p>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-brume"><div className="h-full rounded-full bg-emeraude" style={{ width: `${pct}%` }} /></div>
      {peut && <div className="mt-2 grid gap-x-2 sm:grid-cols-4">
        <Liste libelle="Séance" valeur={n.type} onChange={(x) => setN({ ...n, type: x })} vide={null} options={[{ valeur: "conduite", libelle: "Conduite" }, { valeur: "code", libelle: "Code" }]} />
        <Texte libelle="Durée (min)" type="number" valeur={n.duree_min} onChange={(x) => setN({ ...n, duree_min: x })} min="15" /><Texte libelle="Thème" valeur={n.theme} onChange={(x) => setN({ ...n, theme: x })} />
        <Liste libelle="Appréciation" valeur={n.appreciation} onChange={(x) => setN({ ...n, appreciation: x })} vide="—" options={[{ valeur: "insuffisant", libelle: "Insuffisant" }, { valeur: "en_progres", libelle: "En progrès" }, { valeur: "acquis", libelle: "Acquis" }, { valeur: "maitrise", libelle: "Maîtrisé" }]} /></div>}
      {peut && <Bouton icone={Save} variante="vert" petit onClick={ajouter}>Enregistrer la séance</Bouton>}
      {l.seances.length > 0 && <table className="tableau mt-2"><thead><tr><th>Date</th><th>Type</th><th className="num">Min</th><th>Thème</th><th>Moniteur</th></tr></thead><tbody>{l.seances.slice(0, 8).map((s) => <tr key={s.id}><td>{dateFr(s.date)}</td><td>{s.type === "code" ? "Code" : "Conduite"}</td><td className="num">{s.duree_min}</td><td>{s.theme}</td><td>{s.moniteur}</td></tr>)}</tbody></table>}
      {ex.length > 0 && <><h3 className="mt-3 text-sm font-semibold">Examens</h3><ul className="mt-1 space-y-1 text-sm">{ex.map((i) => <li key={i.id} className="flex items-center gap-2">{dateFr(i.date)} · {i.epreuve} ({i.type === "externe" ? "externe" : "interne"}) · tentative {i.tentative} <Pastille couleur={{ admis: "vert", ajourne: "rouge", absent: "orange" }[i.statut] || "gris"}>{{ admis: "Admis", ajourne: "Ajourné", absent: "Absent", inscrit: "Inscrit" }[i.statut]}</Pastille></li>)}</ul></>}
    </section>
  );
}

/** Dossier d'un élève : identité, pièces, échéancier, statut, paiements et encaissement. */
function Dossier({ id, onFermer, onChange }) {
  const { parametres, toast, avecToast } = useApp();
  const [e, setE] = useState(null);
  const [recu, setRecu] = useState("");
  const [pay, setPay] = useState({ montant: "", mode: "especes", reference: "" });
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => api(`/eleves/${id}`).then(setE), [id]);
  useEffect(() => { charger().catch((x) => toast(x.message, "erreur")); }, [charger, toast]);
  if (!e) return <Modal titre="Dossier de l'élève" onFermer={onFermer}><div className="py-8 flex justify-center"><span className="jauge" /></div></Modal>;
  const finance = e.paiements !== undefined;
  const basculerPiece = (cle, ok) => avecToast("Enregistrement de la pièce", () => api(`/eleves/${id}`, { methode: "PUT", corps: { pieces: { [cle]: ok } } }).then((r) => { setE({ ...e, ...r }); onChange(); }), () => "Pièce enregistrée");
  const statut = (s) => avecToast("Changement de statut", () => api(`/eleves/${id}/statut`, { methode: "POST", corps: { statut: s } }).then(() => { charger(); onChange(); }), () => "Statut mis à jour").catch(() => {});
  const encaisser = () => avecToast("Enregistrement du paiement", () => api(`/eleves/${id}/paiements`, { methode: "POST", corps: pay }).then((p) => { setPay({ montant: "", mode: "especes", reference: "" }); charger(); onChange(); return p; }),
    (p) => `Paiement enregistré : reçu ${p.recu}`).catch(() => {});
  const annuler = (p) => { const motif = window.prompt(`Motif de l'annulation du reçu ${p.recu} :`); if (motif) avecToast("Annulation du paiement", () => api(`/paiements/${p.id}/annuler`, { methode: "POST", corps: { motif } }).then(() => { charger(); onChange(); }), () => "Paiement annulé").catch(() => {}); };
  return (
    <>
      <Modal titre={`${e.nom} ${e.prenom}`} large onFermer={onFermer} pied={<Bouton onClick={onFermer}>Fermer</Bouton>}>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-bold text-emeraude">{e.matricule}</span><Pastille couleur={STATUTS[e.statut][1]}>{STATUTS[e.statut][0]}</Pastille>
          <Pastille couleur="bleu">Permis {e.categorie}</Pastille>{e.dossier_complet ? <Pastille couleur="vert" icone={BadgeCheck}>Dossier complet</Pastille> : <Pastille couleur="orange">Pièces manquantes</Pastille>}
        </div>
        <p className="mt-2 text-sm text-ardoise">{e.telephone}{e.email && ` · ${e.email}`} · né(e) le {dateFr(e.date_naissance)} · {e.agence_nom}</p>
        <Liste libelle="Statut de formation" valeur={e.statut} onChange={statut} vide={null} options={Object.entries(STATUTS).map(([k, [l]]) => ({ valeur: k, libelle: l }))} />
        {finance && <div className="mb-3 grid grid-cols-3 gap-2 text-center text-sm">
          <div className="rounded-xl bg-brume p-2"><p className="text-xs text-ardoise">À payer</p><p className="font-bold tabular-nums">{m(e.net_a_payer)}</p></div>
          <div className="rounded-xl bg-emerald-50 p-2"><p className="text-xs text-ardoise">Payé</p><p className="font-bold tabular-nums text-emerald-700">{m(e.paye)}</p></div>
          <div className="rounded-xl bg-rose-50 p-2"><p className="text-xs text-ardoise">Reste dû</p><p className="font-bold tabular-nums text-rose-700">{m(e.reste_du)}</p></div></div>}
        {e.promotion && <p className="mb-2 text-xs text-ardoise">Promotion {e.promotion} : remise de {m(e.remise)} sur {m(e.prix)}</p>}
        <p className="mb-1 text-xs font-semibold text-ardoise">Pièces du dossier (cochez dès réception)</p>
        {(parametres?.pieces || []).map((p) => <Case key={p.cle} libelle={`${p.libelle}${p.obligatoire ? " *" : ""}`} valeur={e.pieces?.[p.cle]} onChange={(x) => basculerPiece(p.cle, x)} />)}
        <Livret id={id} statut={e.statut} />
        {finance && e.reste_du > 0 && e.statut !== "abandon" && (
          <div className="mt-3 rounded-2xl bg-brume p-3">
            <p className="mb-2 text-sm font-semibold">Encaisser un paiement</p>
            <div className="grid gap-x-3 sm:grid-cols-3">
              <Texte libelle="Montant" type="number" valeur={pay.montant} onChange={(x) => setPay({ ...pay, montant: x })} min="0" max={e.reste_du} />
              <Liste libelle="Mode" valeur={pay.mode} onChange={(x) => setPay({ ...pay, mode: x })} vide={null} options={(parametres?.modes_paiement || []).map((x) => ({ valeur: x.cle, libelle: x.libelle }))} />
              <Texte libelle="Référence" valeur={pay.reference} onChange={(x) => setPay({ ...pay, reference: x })} placeholder={pay.mode === "especes" ? "(facultatif)" : "N° de transaction"} />
            </div>
            <Bouton icone={CreditCard} variante="vert" petit onClick={encaisser} disabled={!pay.montant}>Encaisser</Bouton>
          </div>)}
        {finance && <>
          <h3 className="mt-4 text-sm font-semibold">Paiements</h3>
          <table className="tableau mt-1"><thead><tr><th>Reçu</th><th>Date</th><th>Mode</th><th className="num">Montant</th><th /></tr></thead>
            <tbody>{e.paiements.map((p) => (
              <tr key={p.id} className={p.annule ? "opacity-50 line-through" : ""}><td className="font-semibold text-emeraude">{p.recu}</td><td>{dateFr(p.date)}</td><td>{p.mode_libelle}</td><td className="num text-emerald-700">{m(p.montant)}</td>
                <td className="whitespace-nowrap"><BoutonIcone icone={Eye} libelle="Voir le reçu" onClick={() => setRecu(p.id)} />{!p.annule && <button className="ml-1 text-xs text-rose-700 underline" onClick={() => annuler(p)}>Annuler</button>}</td></tr>))}
              {!e.paiements.length && <tr><td colSpan={5} className="text-slate-500">Aucun paiement.</td></tr>}</tbody></table></>}
      </Modal>
      {recu && <PdfInterne titre="Reçu de paiement" chemin={`/paiements/${recu}/recu`} onFermer={() => setRecu("")} />}
    </>
  );
}

export default function Eleves() {
  const { parametres, utilisateur, avecToast } = useApp();
  const [liste, setListe] = useState(null);
  const [q, setQ] = useState("");
  const [filtres, setFiltres] = useState({ statut: "actifs", categorie: "", impaye: false });
  const [page, setPage] = useState(1);
  const [ouvert, setOuvert] = useState("");
  const [inscrire, setInscrire] = useState(false);
  const tri = useTri();
  const peutEcrire = ["super_admin", "directeur", "gestionnaire", "secretaire"].includes(utilisateur.role);
  const finance = utilisateur.role !== "moniteur";
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => {
    const p = new URLSearchParams({ q, statut: filtres.statut, categorie: filtres.categorie, impaye: filtres.impaye, page, limite: 30, tri: SERVEUR[tri.cle] || "date", sens: tri.sens === 1 ? "asc" : "desc" });
    return api(`/eleves?${p}`).then(setListe);
  }, [q, filtres, page, tri.cle, tri.sens]);
  useEffect(() => { const t = setTimeout(() => charger().catch(() => {}), 250); return () => clearTimeout(t); }, [charger]);
  const pages = liste ? Math.max(1, Math.ceil(liste.total / liste.limite)) : 1;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Élèves</h1>
        <div className="flex gap-2">
          <Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation de la liste", charger, () => `${liste?.total ?? 0} élève(s)`)}>Actualiser</Bouton>
          {peutEcrire && <Bouton icone={Plus} variante="principal" petit onClick={() => setInscrire(true)}>Inscrire un élève</Bouton>}
        </div>
      </div>
      <div className="mt-3 grid gap-x-3 sm:grid-cols-4">
        <Champ libelle="Rechercher (nom, matricule, téléphone)"><div className="relative"><Search size={16} className="absolute left-3 top-3 text-slate-400" /><input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className={`${classeChamp} pl-9`} /></div></Champ>
        <Liste libelle="Statut" valeur={filtres.statut} onChange={(x) => { setFiltres({ ...filtres, statut: x }); setPage(1); }} vide="Tous" options={[{ valeur: "actifs", libelle: "En cours de formation" }, ...Object.entries(STATUTS).map(([k, [l]]) => ({ valeur: k, libelle: l }))]} />
        <Liste libelle="Catégorie" valeur={filtres.categorie} onChange={(x) => { setFiltres({ ...filtres, categorie: x }); setPage(1); }} vide="Toutes" options={(parametres?.categories || []).map((c) => c.code)} />
        {finance && <div className="pt-6"><Case libelle="Avec reste dû seulement" valeur={filtres.impaye} onChange={(x) => { setFiltres({ ...filtres, impaye: x }); setPage(1); }} /></div>}
      </div>
      {!liste ? <div className="py-10 flex justify-center"><span className="jauge" /></div> : (
        <div className="rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
          <table className="tableau"><thead><tr>
            <ThTri cle="matricule" tri={tri}>Matricule</ThTri><ThTri cle="nom" tri={tri}>Élève</ThTri><ThTri cle="categorie" tri={tri}>Permis</ThTri><ThTri cle="statut" tri={tri}>Statut</ThTri><ThTri cle="date" tri={tri}>Inscrit le</ThTri>
            {finance && <><ThTri cle="net" tri={tri} numerique>À payer</ThTri><th className="num">Payé</th><th className="num">Reste dû</th></>}<th>Dossier</th><th /></tr></thead>
            <tbody>{liste.eleves.map((e) => (
              <tr key={e.id} className={ouvert === e.id ? "ligne-selectionnee" : ""} onDoubleClick={() => setOuvert(e.id)}>
                <td className="font-semibold text-emeraude">{e.matricule}</td><td>{e.nom} {e.prenom}<div className="text-xs text-slate-500">{e.telephone}</div></td><td>{e.categorie}</td>
                <td><Pastille couleur={STATUTS[e.statut]?.[1]}>{STATUTS[e.statut]?.[0] || e.statut}</Pastille></td><td>{dateFr(e.date_inscription)}</td>
                {finance && <><td className="num">{m(e.net_a_payer)}</td><td className="num text-emerald-700">{m(e.paye)}</td><td className={`num font-semibold ${e.reste_du > 0 ? "text-rose-700" : "text-emerald-700"}`}>{m(e.reste_du)}</td></>}
                <td>{e.dossier_complet ? <Pastille couleur="vert" icone={BadgeCheck}>Complet</Pastille> : <Pastille couleur="orange">Incomplet</Pastille>}</td>
                <td><BoutonIcone icone={Eye} libelle="Ouvrir le dossier" onClick={() => setOuvert(e.id)} /></td></tr>))}
              {!liste.eleves.length && <tr><td colSpan={10} className="text-slate-500">Aucun élève ne correspond.</td></tr>}</tbody>
            {/* Ligne de totaux collée sous le tableau (règle 25) : nombre de lignes affichées dans la première colonne, montants à droite */}
            {finance && <tfoot><tr className="font-bold bg-brume"><td>{liste.total} élève(s)</td><td colSpan={4} /><td className="num">{m(liste.totaux.net)}</td><td className="num">{m(liste.totaux.paye)}</td><td className="num">{m(liste.totaux.reste_du)}</td><td colSpan={2} /></tr></tfoot>}
          </table>
        </div>)}
      {liste && pages > 1 && <div className="mt-3 flex items-center justify-center gap-3 text-sm"><Bouton petit disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Bouton><span>Page {page} / {pages}</span><Bouton petit disabled={page >= pages} onClick={() => setPage(page + 1)}>Suivant</Bouton></div>}
      {inscrire && <Inscription onFermer={() => setInscrire(false)} onFait={(r) => { setInscrire(false); charger(); setOuvert(r.id); }} />}
      {ouvert && <Dossier id={ouvert} onFermer={() => setOuvert("")} onChange={charger} />}
    </div>
  );
}
