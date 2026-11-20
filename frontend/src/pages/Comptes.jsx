// Gestion des comptes : création, rôle, agence, activation, mot de passe provisoire (œil, règle 22). Détails dans des fenêtres modales.
import { KeyRound, Plus, Power, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import ChampMotDePasse from "../composants/ChampMotDePasse.jsx";
import ForceMotDePasse from "../composants/ForceMotDePasse.jsx";
import { Champ, Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { trierLignes, useTri } from "../lib/tri.js";

const ROLES = [["directeur", "Directeur"], ["gestionnaire", "Responsable d'agence"], ["secretaire", "Secrétaire"], ["comptable", "Comptable"], ["moniteur", "Moniteur"], ["mecanicien", "Mécanicien"]];

function CompteModal({ onFermer, onFait }) {
  const { avecToast, utilisateur } = useApp();
  const [agences, setAgences] = useState([]);
  const f = useFormulaire({ login: "", nom_affiche: "", role: "", agence_id: "", mot_de_passe: "" });
  useEffect(() => { if (utilisateur.ecole_id || !utilisateur.plateforme) api("/agences").then(setAgences).catch(() => {}); }, [utilisateur]);
  const v = f.valeurs;
  const enregistrer = () => avecToast("Création du compte", () => api("/comptes", { methode: "POST", corps: v }), () => "Compte créé").then(onFait).catch(() => {});
  return (
    <Modal titre="Nouveau compte" onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!f.modifie} onClick={enregistrer}>Créer le compte</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Texte libelle="Identifiant *" valeur={v.login} onChange={(x) => f.maj("login", x)} placeholder="awa.badini@gmail.com" /><Texte libelle="Nom affiché *" valeur={v.nom_affiche} onChange={(x) => f.maj("nom_affiche", x)} placeholder="BADINI Awa" />
      <Liste libelle="Rôle *" valeur={v.role} onChange={(x) => f.maj("role", x)} options={ROLES.map(([k, l]) => ({ valeur: k, libelle: l }))} />
      <Liste libelle="Agence (facultatif : limite l'accès à cette agence)" valeur={v.agence_id} onChange={(x) => f.maj("agence_id", x)} options={agences.map((a) => ({ valeur: a.id, libelle: a.nom }))} vide="Toutes les agences" />
      <Champ libelle="Mot de passe provisoire *"><ChampMotDePasse valeur={v.mot_de_passe} onChange={(x) => f.maj("mot_de_passe", x)} autoComplete="new-password" /></Champ><ForceMotDePasse valeur={v.mot_de_passe} />
    </Modal>
  );
}

function Reinit({ compte, onFermer }) {
  const { avecToast } = useApp();
  const [mdp, setMdp] = useState("");
  const go = () => avecToast("Réinitialisation", () => api(`/comptes/${compte.id}/reinitialiser`, { methode: "POST", corps: { mot_de_passe: mdp } }), () => "Mot de passe provisoire enregistré").then(onFermer).catch(() => {});
  return (
    <Modal titre={`Mot de passe de ${compte.login}`} onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!mdp} onClick={go}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Champ libelle="Nouveau mot de passe provisoire (à changer à la prochaine connexion)"><ChampMotDePasse valeur={mdp} onChange={setMdp} autoComplete="new-password" /></Champ><ForceMotDePasse valeur={mdp} />
    </Modal>
  );
}

export default function Comptes() {
  const { avecToast, utilisateur } = useApp();
  const [liste, setListe] = useState(null);
  const [nouveau, setNouveau] = useState(false);
  const [reinit, setReinit] = useState(null);
  const tri = useTri();
  const charger = useCallback(() => api("/comptes").then(setListe), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const basculer = (c) => avecToast("Mise à jour", () => api(`/comptes/${c.id}`, { methode: "PUT", corps: { actif: !c.actif } }), () => (c.actif ? "Compte désactivé" : "Compte activé")).then(charger).catch(() => {});
  if (!liste) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Gestion des comptes</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation", charger, () => "Liste actualisée")}>Actualiser</Bouton>{!utilisateur.plateforme || utilisateur.ecole_id ? <Bouton icone={Plus} variante="principal" petit onClick={() => setNouveau(true)}>Nouveau compte</Bouton> : null}</div></div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="login" tri={tri}>Identifiant</ThTri><ThTri cle="nom_affiche" tri={tri}>Nom</ThTri><ThTri cle="role_libelle" tri={tri}>Rôle</ThTri>{utilisateur.plateforme && <ThTri cle="ecole_nom" tri={tri}>Auto-école</ThTri>}<ThTri cle="created_at" tri={tri}>Créé le</ThTri><th>État</th><th /></tr></thead>
          <tbody>{trierLignes(liste, tri.cle, tri.sens).map((c) => (
            <tr key={c.id}><td className="font-semibold text-emeraude">{c.login}</td><td>{c.nom_affiche}</td><td>{c.role_libelle}</td>{utilisateur.plateforme && <td>{c.ecole_nom}</td>}<td>{(c.created_at || "").slice(0, 10)}</td>
              <td>{c.actif ? <Pastille couleur="vert">Actif</Pastille> : <Pastille>Désactivé</Pastille>}</td>
              <td className="whitespace-nowrap">{c.id !== utilisateur.id && <><BoutonIcone icone={KeyRound} libelle="Mot de passe provisoire" onClick={() => setReinit(c)} /><BoutonIcone icone={Power} libelle={c.actif ? "Désactiver" : "Activer"} couleur={c.actif ? "text-rose-600" : "text-emerald-600"} onClick={() => basculer(c)} /></>}</td></tr>))}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{liste.length} compte(s)</td><td colSpan={utilisateur.plateforme ? 6 : 5} /></tr></tfoot></table>
      </div>
      {nouveau && <CompteModal onFermer={() => setNouveau(false)} onFait={() => { setNouveau(false); charger(); }} />}
      {reinit && <Reinit compte={reinit} onFermer={() => setReinit(null)} />}
    </div>
  );
}
