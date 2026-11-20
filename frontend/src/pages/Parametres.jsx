// Paramètres de l'auto-école : présentation (papier à en-tête des reçus), catégories de permis, épreuves d'examen, pièces à fournir, modes de paiement, agences.
// Chaque bloc a son bouton « Enregistrer » (actif seulement si modifié, mention « modifié, non enregistré » : règle 15). Rien n'est figé pour un pays.
import { Plus, Power, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Case, Liste, Pastille, Texte } from "../composants/Champs.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";

/** Cadre d'un bloc de réglages avec son bouton Enregistrer. */
function Bloc({ titre, modifie, onEnregistrer, children, aide }) {
  return (
    <section className="mb-4 rounded-2xl bg-white p-4 ring-1 ring-encre/5">
      <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">{titre}</h2>
        <div className="flex items-center gap-2">{modifie && <span className="text-xs text-orange-700">modifié, non enregistré</span>}<Bouton icone={Save} variante="principal" petit disabled={!modifie} onClick={onEnregistrer}>Enregistrer</Bouton></div></div>
      {aide && <p className="mb-2 text-xs text-ardoise">{aide}</p>}{children}
    </section>
  );
}

/** Liste modifiable de lignes {…} : `colonnes` = [{cle, libelle, type?}] ; ajout et retrait de lignes. */
function Lignes({ lignes, onChange, colonnes, vide }) {
  const maj = (i, cle, v) => onChange(lignes.map((l, j) => (j === i ? { ...l, [cle]: v } : l)));
  return (
    <div className="mt-2 space-y-2">
      {lignes.map((l, i) => (
        <div key={i} className="flex flex-wrap items-end gap-2">
          {colonnes.map((c) => c.type === "case"
            ? <div key={c.cle} className="pb-1"><Case libelle={c.libelle} valeur={l[c.cle]} onChange={(v) => maj(i, c.cle, v)} /></div>
            : <div key={c.cle} className={c.large ? "min-w-[12rem] flex-1" : "w-28"}><Texte libelle={c.libelle} type={c.type} valeur={l[c.cle]} onChange={(v) => maj(i, c.cle, v)} /></div>)}
          <div className="pb-3"><BoutonIcone icone={Trash2} libelle="Retirer cette ligne" couleur="text-rose-600" onClick={() => onChange(lignes.filter((_, j) => j !== i))} /></div>
        </div>))}
      <Bouton icone={Plus} petit onClick={() => onChange([...lignes, Object.fromEntries(colonnes.map((c) => [c.cle, c.type === "case" ? false : ""]))])}>Ajouter</Bouton>
      {!lignes.length && vide && <p className="text-xs text-slate-500">{vide}</p>}
    </div>
  );
}

export default function Parametres() {
  const { parametres, rechargerParametres, avecToast, utilisateur } = useApp();
  const [p, setP] = useState(null);
  const [origine, setOrigine] = useState(null);
  const [agences, setAgences] = useState([]);
  const [nouvelleAgence, setNouvelleAgence] = useState("");
  useEffect(() => { if (parametres) { setP(structuredClone(parametres)); setOrigine(structuredClone(parametres)); } }, [parametres]);
  const chargerAgences = () => api("/agences").then(setAgences);
  useEffect(() => { chargerAgences().catch(() => {}); }, []);
  if (!p) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const modifie = (...cles) => cles.some((c) => JSON.stringify(p[c]) !== JSON.stringify(origine[c]));
  const enregistrer = (nom, ...cles) => avecToast(`Enregistrement : ${nom}`, () => api("/ecole", { methode: "PUT", corps: Object.fromEntries(cles.map((c) => [c, p[c]])) }), () => `${nom} : enregistré`).then(() => rechargerParametres()).catch(() => {});
  const maj = (cle, v) => setP({ ...p, [cle]: v });
  const ajouterAgence = () => avecToast("Création de l'agence", () => api("/agences", { methode: "POST", corps: { nom: nouvelleAgence } }), () => "Agence créée").then(() => { setNouvelleAgence(""); chargerAgences(); }).catch(() => {});
  const basculerAgence = (a) => avecToast("Mise à jour de l'agence", () => api(`/agences/${a.id}`, { methode: "PUT", corps: { actif: !a.actif } }), () => (a.actif ? "Agence désactivée" : "Agence activée")).then(chargerAgences).catch(() => {});
  const MODES = [["especes", "Espèces"], ["mobile_money", "Mobile money"], ["virement", "Virement"], ["cheque", "Chèque"], ["carte", "Carte bancaire"]];
  const modesActifs = new Set(p.modes_paiement.map((m) => m.cle));
  return (
    <div>
      <h1 className="text-2xl font-bold">Paramètres de l'auto-école</h1>
      <p className="mb-3 text-sm text-ardoise">{p.nom} · {p.pays} · devise {p.devise}. Les catégories, épreuves et pièces ci-dessous sont des points de départ : adaptez-les à la réglementation de votre pays.</p>
      <Bloc titre="Présentation (papier à en-tête des reçus)" modifie={modifie("nom", "telephone", "email", "adresse", "ville", "identifiant_fiscal", "agrement", "responsable")} onEnregistrer={() => enregistrer("Présentation", "nom", "telephone", "email", "adresse", "ville", "identifiant_fiscal", "agrement", "responsable")}>
        <div className="grid gap-x-3 sm:grid-cols-2 lg:grid-cols-3">
          {[["nom", "Nom"], ["responsable", "Responsable"], ["telephone", "Téléphone"], ["email", "E-mail"], ["adresse", "Adresse"], ["ville", "Ville"], ["identifiant_fiscal", "IFU / RCCM"], ["agrement", "N° d'agrément"]].map(([k, l]) => <Texte key={k} libelle={l} valeur={p[k]} onChange={(x) => maj(k, x)} />)}
        </div>
      </Bloc>
      <Bloc titre="Catégories de permis" modifie={modifie("categories")} onEnregistrer={() => enregistrer("Catégories", "categories")} aide="Code court (A, B, C…), libellé et âge minimum légal dans votre pays.">
        <Lignes lignes={p.categories} onChange={(v) => maj("categories", v)} colonnes={[{ cle: "code", libelle: "Code" }, { cle: "libelle", libelle: "Libellé", large: true }, { cle: "age_min", libelle: "Âge min.", type: "number" }]} />
      </Bloc>
      <Bloc titre="Épreuves d'examen" modifie={modifie("epreuves")} onEnregistrer={() => enregistrer("Épreuves", "epreuves")} aide="Les épreuves que vos élèves passent (code, créneau, conduite, circuit, manœuvres…).">
        <Lignes lignes={p.epreuves} onChange={(v) => maj("epreuves", v)} colonnes={[{ cle: "code", libelle: "Code" }, { cle: "libelle", libelle: "Libellé", large: true }]} />
      </Bloc>
      <Bloc titre="Pièces à fournir" modifie={modifie("pieces")} onEnregistrer={() => enregistrer("Pièces", "pieces")} aide="Un dossier est complet quand toutes les pièces obligatoires sont reçues (obligatoire pour passer « prêt pour l'examen »).">
        <Lignes lignes={p.pieces} onChange={(v) => maj("pieces", v)} colonnes={[{ cle: "cle", libelle: "Clé" }, { cle: "libelle", libelle: "Libellé", large: true }, { cle: "obligatoire", libelle: "Obligatoire", type: "case" }]} />
      </Bloc>
      <Bloc titre="Modes de paiement acceptés" modifie={modifie("modes_paiement")} onEnregistrer={() => enregistrer("Modes de paiement", "modes_paiement")}>
        <div className="mt-2 grid sm:grid-cols-3">{MODES.map(([k, l]) => <Case key={k} libelle={l} valeur={modesActifs.has(k)} onChange={(on) => maj("modes_paiement", MODES.filter(([c]) => (c === k ? on : modesActifs.has(c))).map(([c, lib]) => ({ cle: c, libelle: lib })))} />)}</div>
      </Bloc>
      {["super_admin", "directeur"].includes(utilisateur.role) && (
        <section className="mb-4 rounded-2xl bg-white p-4 ring-1 ring-encre/5">
          <h2 className="font-semibold">Agences</h2>
          <ul className="mt-2 divide-y divide-slate-100 text-sm">{agences.map((a) => <li key={a.id} className="flex items-center justify-between py-1.5"><span>{a.nom} {a.principale && <Pastille couleur="bleu">Principale</Pastille>} {!a.actif && <Pastille>Désactivée</Pastille>}</span>
            {!a.principale && <BoutonIcone icone={Power} libelle={a.actif ? "Désactiver" : "Activer"} couleur={a.actif ? "text-rose-600" : "text-emerald-600"} onClick={() => basculerAgence(a)} />}</li>)}</ul>
          <div className="mt-3 flex items-end gap-2"><div className="flex-1"><Texte libelle="Nouvelle agence" valeur={nouvelleAgence} onChange={setNouvelleAgence} placeholder="Agence de Bobo-Dioulasso" /></div><div className="pb-3"><Bouton icone={Plus} petit disabled={!nouvelleAgence.trim()} onClick={ajouterAgence}>Ajouter</Bouton></div></div>
        </section>)}
    </div>
  );
}
