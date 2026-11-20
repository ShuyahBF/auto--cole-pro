// Transferts de dossiers : entre agences, vers une autre auto-école (dossier PDF), depuis une autre auto-école. Fenêtres modales (règle 20).
import { ArrowLeftRight, FileText, Plus, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Case, Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import PdfInterne from "../composants/PdfInterne.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { dateFr } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

/** Choix d'un élève actif par recherche (nom ou matricule). */
function ChoixEleve({ onChoisir, choisi }) {
  const [q, setQ] = useState("");
  const [l, setL] = useState([]);
  useEffect(() => { const t = setTimeout(() => q.length > 1 && api(`/eleves?q=${encodeURIComponent(q)}&statut=actifs&limite=8`).then((r) => setL(r.eleves)).catch(() => {}), 250); return () => clearTimeout(t); }, [q]);
  return (
    <div className="mb-3"><Texte libelle="Élève (nom ou matricule) *" valeur={choisi ? `${choisi.nom} ${choisi.prenom} (${choisi.matricule})` : q} onChange={(x) => { onChoisir(null); setQ(x); }} />
      {!choisi && l.length > 0 && <ul className="-mt-2 rounded-lg border border-slate-200 bg-white text-sm">{l.map((e) => <li key={e.id}><button className="block w-full px-3 py-1.5 text-left hover:bg-sky-100/60" onClick={() => onChoisir(e)}>{e.nom} {e.prenom} <span className="text-xs text-slate-500">{e.matricule}</span></button></li>)}</ul>}</div>
  );
}

function Nouveau({ type, onFermer, onFait }) {
  const { parametres, avecToast } = useApp();
  const [eleve, setEleve] = useState(null);
  const [agences, setAgences] = useState([]);
  const [tarifs, setTarifs] = useState([]);
  const f = useFormulaire({ agence_id: "", motif: "", ecole_destination: "", accepter_solde: false, ecole_origine: "", heures_deja_faites: 0, nom: "", prenom: "", date_naissance: "", telephone: "", categorie: "", tarif_id: "" });
  useEffect(() => { api("/agences").then(setAgences); api("/tarifs").then(setTarifs); }, []);
  const v = f.valeurs;
  const corps = type === "entrant" ? { ...v } : { ...v, eleve_id: eleve?.id };
  const titre = { agence: "Transfert entre agences", sortant: "Transfert vers une autre auto-école", entrant: "Élève venu d'une autre auto-école" }[type];
  const enregistrer = () => avecToast("Enregistrement du transfert", () => api(`/transferts/${type}`, { methode: "POST", corps }), () => "Transfert enregistré").then(onFait).catch(() => {});
  return (
    <Modal titre={titre} onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" onClick={enregistrer}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      {type !== "entrant" && <ChoixEleve choisi={eleve} onChoisir={setEleve} />}
      {type === "agence" && <Liste libelle="Agence de destination *" valeur={v.agence_id} onChange={(x) => f.maj("agence_id", x)} options={agences.filter((a) => a.actif).map((a) => ({ valeur: a.id, libelle: a.nom }))} />}
      {type === "sortant" && <><Texte libelle="Auto-école de destination *" valeur={v.ecole_destination} onChange={(x) => f.maj("ecole_destination", x)} /><Case libelle="J'accepte que le solde restant dû soit noté dans le transfert" valeur={v.accepter_solde} onChange={(x) => f.maj("accepter_solde", x)} /></>}
      {type === "entrant" && <>
        <Texte libelle="Auto-école d'origine *" valeur={v.ecole_origine} onChange={(x) => f.maj("ecole_origine", x)} /><Texte libelle="Heures de conduite déjà effectuées" type="number" valeur={v.heures_deja_faites} onChange={(x) => f.maj("heures_deja_faites", x)} min="0" />
        <div className="grid grid-cols-2 gap-x-3"><Texte libelle="Nom *" valeur={v.nom} onChange={(x) => f.maj("nom", x)} /><Texte libelle="Prénom(s) *" valeur={v.prenom} onChange={(x) => f.maj("prenom", x)} />
          <Texte libelle="Date de naissance *" type="date" valeur={v.date_naissance} onChange={(x) => f.maj("date_naissance", x)} /><Texte libelle="Téléphone *" valeur={v.telephone} onChange={(x) => f.maj("telephone", x)} />
          <Liste libelle="Catégorie *" valeur={v.categorie} onChange={(x) => f.setValeurs((s) => ({ ...s, categorie: x, tarif_id: "" }))} options={(parametres?.categories || []).map((c) => c.code)} />
          <Liste libelle="Forfait *" valeur={v.tarif_id} onChange={(x) => f.maj("tarif_id", x)} options={tarifs.filter((t) => t.actif && t.categorie === v.categorie).map((t) => ({ valeur: t.id, libelle: t.libelle }))} /></div></>}
      <Texte libelle="Motif" valeur={v.motif} onChange={(x) => f.maj("motif", x)} />
    </Modal>
  );
}

export default function Transferts() {
  const { avecToast } = useApp();
  const [liste, setListe] = useState(null);
  const [type, setType] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [pdf, setPdf] = useState("");
  const tri = useTri();
  const charger = useCallback(() => api("/transferts").then(setListe), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  if (!liste) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const lignes = trierLignes(liste, tri.cle, tri.sens);
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Transferts de dossiers</h1>
        <div className="flex flex-wrap gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des transferts", charger, (r) => "Transferts actualisés")}>Actualiser</Bouton>
          <Bouton icone={ArrowLeftRight} petit onClick={() => setNouveau("agence")}>Entre agences</Bouton><Bouton icone={Plus} petit onClick={() => setNouveau("sortant")}>Vers une autre école</Bouton><Bouton icone={Plus} variante="principal" petit onClick={() => setNouveau("entrant")}>Depuis une autre école</Bouton></div></div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto"><table className="tableau"><thead><tr><ThTri cle="date" tri={tri}>Date</ThTri><ThTri cle="type_libelle" tri={tri}>Type</ThTri><ThTri cle="matricule" tri={tri}>Matricule</ThTri><ThTri cle="eleve_nom" tri={tri}>Élève</ThTri><th>De / vers</th><ThTri cle="motif" tri={tri}>Motif</ThTri><ThTri cle="par" tri={tri}>Par</ThTri><ThTri cle="solde_restant" tri={tri} numerique>Solde noté</ThTri><th /></tr></thead>
        <tbody>{lignes.map((t) => (
          <tr key={t.id}><td>{dateFr(t.date)}</td><td><Pastille couleur={t.type === "sortant" ? "violet" : t.type === "entrant" ? "vert" : "bleu"}>{t.type_libelle}</Pastille></td><td className="font-semibold text-emeraude">{t.matricule}</td><td>{t.eleve_nom}</td>
            <td>{t.type === "agence" ? `${t.de_agence} → ${t.vers_agence}` : t.type === "sortant" ? t.ecole_destination : t.ecole_origine}</td><td>{t.motif}</td><td>{t.par}</td><td className="num">{t.solde_restant ?? ""}</td>
            <td>{t.type !== "entrant" && <BoutonIcone icone={FileText} libelle="Dossier de transfert (PDF)" onClick={() => setPdf(t.id)} />}</td></tr>))}
          {!lignes.length && <tr><td colSpan={9} className="text-slate-500">Aucun transfert.</td></tr>}</tbody>
        <tfoot><tr className="font-bold bg-brume"><td>{lignes.length} transfert(s)</td><td colSpan={6} /><td className="num">{lignes.reduce((a, t) => a + (t.solde_restant || 0), 0)}</td><td /></tr></tfoot></table></div>
      {nouveau && <Nouveau type={nouveau} onFermer={() => setNouveau("")} onFait={() => { setNouveau(""); charger(); }} />}
      {pdf && <PdfInterne titre="Dossier de transfert" chemin={`/transferts/${pdf}/dossier`} onFermer={() => setPdf("")} />}
    </div>
  );
}
