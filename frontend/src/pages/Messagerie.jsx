// Centre de messagerie WhatsApp : conversations, envois groupés (convocations, relances, demandes d'avis), modèles, notifications automatiques.
// Les envois partent en arrière-plan : statuts « en cours » → « envoyé » → « remis » → « lu » / « échec ». Aucun montant ni donnée de santé par WhatsApp.
import { MessageCircle, RefreshCw, Save, Send, Users } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Case, Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { dateHeureFr } from "../lib/format.js";
import { sansAccent } from "../lib/tri.js";

const STATUTS = { en_cours: ["En cours…", "gris"], envoye: ["Envoyé", "bleu"], remis: ["Remis", "vert"], lu: ["Lu", "vert"], echec: ["Échec", "rouge"], recu: ["Reçu", "gris"] };

function Groupe({ onFermer }) {
  const { avecToast } = useApp();
  const [cible, setCible] = useState("impayes");
  const [sessions, setSessions] = useState([]);
  const [sid, setSid] = useState("");
  const [apercu, setApercu] = useState(null);
  useEffect(() => { api("/examens/sessions").then(setSessions).catch(() => {}); }, []);
  const corps = { cible, session_id: sid };
  const voir = () => api("/messagerie/groupe", { methode: "POST", corps: { ...corps, apercu: true } }).then(setApercu).catch((e) => avecToast("Aperçu", () => Promise.reject(e)).catch(() => {}));
  const envoyer = () => avecToast("Envoi groupé", () => api("/messagerie/groupe", { methode: "POST", corps }), (r) => `${r.envoyes} message(s) en cours d'envoi, ${r.ignores} ignoré(s)`).then(onFermer).catch(() => {});
  useEffect(() => { setApercu(null); }, [cible, sid]);
  return (
    <Modal titre="Envoi groupé" onFermer={onFermer} pied={<><Bouton icone={Users} petit onClick={voir}>Voir combien</Bouton><Bouton icone={Send} variante="principal" disabled={!apercu || !apercu.a_envoyer} onClick={envoyer}>Envoyer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Liste libelle="Destinataires" valeur={cible} onChange={setCible} vide={null} options={[{ valeur: "impayes", libelle: "Élèves en retard de paiement (rappel sans montant)" }, { valeur: "convocations", libelle: "Inscrits à une session d'examen (convocation)" }, { valeur: "avis", libelle: "Permis obtenus récemment (demande d'avis)" }]} />
      {cible === "convocations" && <Liste libelle="Session d'examen" valeur={sid} onChange={setSid} options={sessions.map((s) => ({ valeur: s.id, libelle: `${s.date} ${s.heure} · ${s.epreuve_libelle} (${s.categorie}) · ${s.inscrits} inscrit(s)` }))} />}
      {apercu && <p className="rounded-xl bg-brume p-3 text-sm"><b>{apercu.a_envoyer}</b> message(s) partiront{apercu.ignores > 0 && <>, <b>{apercu.ignores}</b> élève(s) ignoré(s) (numéro invalide ou désinscrit)</>}. Vérifiez puis cliquez sur « Envoyer ».</p>}
    </Modal>
  );
}

function Modeles({ onFermer }) {
  const { avecToast } = useApp();
  const [l, setL] = useState([]);
  const [edit, setEdit] = useState({});
  const charger = () => api("/messagerie/modeles").then((x) => { setL(x); setEdit({}); });
  useEffect(() => { charger(); }, []);
  return (
    <Modal titre="Modèles de messages" large onFermer={onFermer} pied={<Bouton onClick={onFermer}>Fermer</Bouton>}>
      <p className="mb-2 text-xs text-ardoise">Variables : {"{prenom} {nom} {ecole} {matricule}"} · convocation : {"{examen} {date_examen} {heure_examen} {lieu_examen}"} · avis : {"{lien_avis}"}</p>
      {l.map((m) => (
        <div key={m.id} className="mb-3"><p className="text-sm font-semibold">{m.nom}</p>
          <textarea className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" rows={3} value={edit[m.id] ?? m.texte} onChange={(e) => setEdit({ ...edit, [m.id]: e.target.value })} />
          <div className="flex items-center gap-2">{edit[m.id] !== undefined && edit[m.id] !== m.texte && <><span className="text-xs text-orange-700">modifié, non enregistré</span>
            <Bouton icone={Save} variante="principal" petit onClick={() => avecToast("Enregistrement du modèle", () => api(`/messagerie/modeles/${m.id}`, { methode: "PUT", corps: { texte: edit[m.id] } }), () => "Modèle enregistré").then(charger)}>Enregistrer</Bouton></>}</div></div>))}
    </Modal>
  );
}

function Auto({ onFermer }) {
  const { avecToast, utilisateur } = useApp();
  const [p, setP] = useState(null);
  const [auto, setAuto] = useState({});
  useEffect(() => { api("/messagerie/parametres").then((x) => { setP(x); setAuto(x.auto); }); }, []);
  if (!p) return null;
  const peut = ["directeur", "super_admin"].includes(utilisateur.role);
  const modifie = JSON.stringify(auto) !== JSON.stringify(p.auto);
  return (
    <Modal titre="Notifications automatiques" onFermer={onFermer} pied={<>{peut && <Bouton icone={Save} variante="principal" disabled={!modifie} onClick={() => avecToast("Enregistrement", () => api("/messagerie/parametres", { methode: "PUT", corps: { auto } }), () => "Réglages enregistrés").then(onFermer)}>Enregistrer</Bouton>}<Bouton onClick={onFermer}>Fermer</Bouton></>}>
      <p className="mb-2 text-xs text-ardoise">Éteintes par défaut. Un message automatique n'est envoyé que si WhatsApp est configuré et si l'élève a un numéro valide, non désinscrit.</p>
      {Object.entries(p.libelles).map(([k, l]) => <Case key={k} libelle={l} valeur={auto[k]} onChange={peut ? (x) => setAuto({ ...auto, [k]: x }) : () => {}} />)}
      {modifie && <p className="text-xs text-orange-700">modifié, non enregistré</p>}
      <p className="mt-3 rounded-xl bg-brume p-2 text-xs text-ardoise">Ligne WhatsApp : {p.wa_emetteur ? `ligne privée « ${p.wa_emetteur} »${p.wa_repli ? " (repli sur la ligne partagée autorisé)" : ""}` : "ligne partagée de la plateforme"}.</p>
    </Modal>
  );
}

export default function Messagerie() {
  const { avecToast, toast } = useApp();
  const [etat, setEtat] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [q, setQ] = useState("");
  const [choisi, setChoisi] = useState(null);
  const [conv, setConv] = useState(null);
  const [texte, setTexte] = useState("");
  const [modale, setModale] = useState("");
  const fin = useRef(null);
  const charger = useCallback(() => Promise.all([api("/messagerie/etat").then(setEtat), api(`/messagerie/contacts?q=${encodeURIComponent(q)}`).then(setContacts)]), [q]);
  const ouvrir = useCallback((c) => api(`/messagerie/contacts/${c.id}/messages`).then((r) => { setConv(r); setTimeout(() => fin.current?.scrollIntoView?.(), 50); }), []);
  useEffect(() => { const t = setTimeout(() => charger().catch(() => {}), 250); return () => clearTimeout(t); }, [charger]);
  // La conversation ouverte est relue toutes les 15 s (statuts de remise, réponses reçues).
  useEffect(() => { if (!choisi) return undefined; ouvrir(choisi).catch(() => {}); const t = setInterval(() => ouvrir(choisi).catch(() => {}), 15000); return () => clearInterval(t); }, [choisi, ouvrir]);
  const envoyer = () => avecToast("Envoi du message", () => api("/messagerie/envoyer", { methode: "POST", corps: { contact_id: choisi.id, texte } }), () => "Message en cours d'envoi").then(() => { setTexte(""); ouvrir(choisi); charger(); }).catch(() => {});
  const importer = () => avecToast("Importation des élèves", () => api("/messagerie/contacts/importer-eleves", { methode: "POST" }), (r) => `${r.crees} contact(s) créé(s), ${r.numeros_invalides} numéro(s) invalide(s)`).then(charger).catch(() => {});
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Centre de messagerie WA</h1>
        <div className="flex flex-wrap gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des conversations", charger, () => "Conversations actualisées")}>Actualiser</Bouton>
          <Bouton icone={Users} petit onClick={importer}>Importer les élèves</Bouton><Bouton icone={Send} petit onClick={() => setModale("groupe")}>Envoi groupé</Bouton><Bouton petit onClick={() => setModale("modeles")}>Modèles</Bouton><Bouton petit onClick={() => setModale("auto")}>Automatique</Bouton></div></div>
      {etat && !etat.configure && <p className="mt-3 rounded-xl bg-orange-50 p-3 text-sm text-orange-900 ring-1 ring-orange-200">WhatsApp n'est pas encore configuré sur le serveur (variables LILUVINE_WA_URL et LILUVINE_WA_HMAC) : vous pouvez préparer les contacts et les modèles, les envois sont désactivés.</p>}
      {etat?.configure && <p className="mt-2 text-xs text-ardoise">Ligne utilisée : {etat.canal === "ligne_ecole" ? "ligne privée de l'école" : "ligne partagée de la plateforme"}.</p>}
      <div className="mt-3 grid gap-3 md:grid-cols-[300px_1fr]">
        <aside className="rounded-2xl bg-white p-3 ring-1 ring-encre/5"><Texte libelle="Rechercher un contact" valeur={q} onChange={setQ} />
          <ul className="max-h-[60dvh] space-y-1 overflow-y-auto text-sm">{contacts.map((c) => (
            <li key={c.id}><button onClick={() => setChoisi(c)} aria-selected={choisi?.id === c.id} className={`flex w-full items-start justify-between gap-2 rounded-xl px-2 py-1.5 text-left hover:bg-sky-100/60 ${choisi?.id === c.id ? "ligne-selectionnee" : ""}`}>
              <span className="min-w-0"><b className="block truncate">{c.nom}</b><span className="block truncate text-xs opacity-70">{c.desinscrit ? "Désinscrit (STOP)" : c.dernier_extrait || c.numero_masque}</span></span>
              {c.non_lus > 0 && <span className="rounded-full bg-citron px-1.5 py-0.5 text-[11px] font-bold text-white" aria-label={`${c.non_lus} non lu(s)`}>{c.non_lus}</span>}</button></li>))}
            {!contacts.length && <li className="text-slate-500">Aucun contact : « Importer les élèves ».</li>}</ul></aside>
        <section className="flex min-h-[50dvh] flex-col rounded-2xl bg-white p-3 ring-1 ring-encre/5">
          {!conv || !choisi ? <div className="m-auto text-center text-sm text-slate-500"><MessageCircle size={36} className="mx-auto mb-2 text-citron" />Choisissez une conversation.</div> : <>
            <p className="border-b border-slate-100 pb-2 font-semibold">{conv.contact.nom} <span className="text-xs font-normal text-slate-500">{conv.contact.numero_masque}</span></p>
            <div className="flex-1 space-y-2 overflow-y-auto py-3" style={{ maxHeight: "50dvh" }}>{conv.messages.map((m) => (
              <div key={m.id} className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${m.sens === "sortant" ? "ml-auto bg-emeraude-50" : "bg-brume"}`}>
                <p className="whitespace-pre-wrap break-words">{m.texte}</p>
                <p className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">{dateHeureFr(m.cree_le)}{m.sens === "sortant" && <Pastille couleur={STATUTS[m.statut]?.[1]}>{STATUTS[m.statut]?.[0] || m.statut}</Pastille>}{m.erreur && <span className="text-rose-700">{m.erreur}</span>}</p></div>))}<div ref={fin} /></div>
            {conv.contact.desinscrit ? <p className="text-sm text-rose-700">Ce contact s'est désinscrit (STOP) : aucun message ne peut lui être envoyé.</p> : (
              <div className="flex items-end gap-2"><textarea value={texte} onChange={(e) => setTexte(e.target.value)} rows={2} placeholder="Votre message…" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <Bouton icone={Send} variante="vert" disabled={!texte.trim() || !etat?.configure} onClick={envoyer}>Envoyer</Bouton></div>)}</>}
        </section>
      </div>
      {modale === "groupe" && <Groupe onFermer={() => { setModale(""); charger(); }} />}{modale === "modeles" && <Modeles onFermer={() => setModale("")} />}{modale === "auto" && <Auto onFermer={() => setModale("")} />}
    </div>
  );
}
