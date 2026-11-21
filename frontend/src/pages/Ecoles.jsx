// Auto-écoles (super administrateur) : liste, création avec premier directeur, activation / désactivation. Le pays donne la devise de départ.
import { Plus, Power, RefreshCw, Save } from "lucide-react";
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

function NouvelleEcole({ onFermer, onFait }) {
  const { avecToast } = useApp();
  const [pays, setPays] = useState([]);
  const f = useFormulaire({ nom: "", prefixe: "", pays: "", ville: "", telephone: "", dl: "", dn: "", dm: "" });
  useEffect(() => { api("/ecoles/pays").then(setPays); }, []);
  const v = f.valeurs;
  const enregistrer = () => avecToast("Création de l'auto-école", () => api("/ecoles", { methode: "POST", corps: { nom: v.nom, prefixe: v.prefixe, pays: v.pays, ville: v.ville, telephone: v.telephone,
    directeur: v.dl ? { login: v.dl, nom_affiche: v.dn, mot_de_passe: v.dm } : undefined } }), () => "Auto-école créée").then(onFait).catch(() => {});
  return (
    <Modal titre="Nouvelle auto-école" large onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!f.modifie} onClick={enregistrer}>Créer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <div className="grid gap-x-3 sm:grid-cols-2">
        <Texte libelle="Nom *" majuscules valeur={v.nom} onChange={(x) => f.maj("nom", x)} placeholder="AUTO-ÉCOLE EXCELLENCE" />
        <Texte libelle="Préfixe des matricules *" valeur={v.prefixe} onChange={(x) => f.maj("prefixe", x.toUpperCase())} placeholder="EXC" maxLength={6} />
        <Liste libelle="Pays *" valeur={v.pays} onChange={(x) => f.maj("pays", x)} options={pays.map((p) => ({ valeur: p.code, libelle: `${p.nom} (${p.devise})` }))} />
        <Texte libelle="Ville" valeur={v.ville} onChange={(x) => f.maj("ville", x)} /><Texte libelle="Téléphone" valeur={v.telephone} onChange={(x) => f.maj("telephone", x)} />
      </div>
      <p className="mb-1 mt-2 text-sm font-semibold">Premier directeur (facultatif)</p>
      <div className="grid gap-x-3 sm:grid-cols-2"><Texte libelle="Identifiant" valeur={v.dl} onChange={(x) => f.maj("dl", x)} placeholder="awa.badini@gmail.com" /><Texte libelle="Nom affiché" valeur={v.dn} onChange={(x) => f.maj("dn", x)} placeholder="BADINI Awa" /></div>
      <Champ libelle="Mot de passe provisoire (à changer à la première connexion)"><ChampMotDePasse valeur={v.dm} onChange={(x) => f.maj("dm", x)} autoComplete="new-password" /></Champ><ForceMotDePasse valeur={v.dm} />
    </Modal>
  );
}

export default function Ecoles() {
  const { rechargerEcoles, avecToast, choisirEcole } = useApp();
  const [liste, setListe] = useState(null);
  const [nouveau, setNouveau] = useState(false);
  const tri = useTri();
  const charger = useCallback(() => api("/ecoles").then((l) => { setListe(l); rechargerEcoles(); }), [rechargerEcoles]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const basculer = (e) => avecToast("Mise à jour", () => api(`/ecoles/${e.id}`, { methode: "PUT", corps: { actif: !e.actif } }), () => (e.actif ? "Auto-école désactivée" : "Auto-école activée")).then(charger).catch(() => {});
  if (!liste) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Auto-écoles</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation", charger, (l) => "Liste actualisée")}>Actualiser</Bouton><Bouton icone={Plus} variante="principal" petit onClick={() => setNouveau(true)}>Nouvelle auto-école</Bouton></div></div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="nom" tri={tri}>Nom</ThTri><ThTri cle="prefixe" tri={tri}>Préfixe</ThTri><ThTri cle="pays" tri={tri}>Pays</ThTri><ThTri cle="devise" tri={tri}>Devise</ThTri><ThTri cle="ville" tri={tri}>Ville</ThTri><th>État</th><th /></tr></thead>
          <tbody>{trierLignes(liste, tri.cle, tri.sens).map((e) => (
            <tr key={e.id}><td className="font-semibold">{e.nom}</td><td className="text-emeraude font-semibold">{e.prefixe}</td><td>{e.pays}</td><td>{e.devise}</td><td>{e.ville}</td><td>{e.actif ? <Pastille couleur="vert">Active</Pastille> : <Pastille>Désactivée</Pastille>}</td>
              <td className="whitespace-nowrap"><Bouton petit onClick={() => choisirEcole(e.id)}>Travailler ici</Bouton> <BoutonIcone icone={Power} libelle={e.actif ? "Désactiver" : "Activer"} couleur={e.actif ? "text-rose-600" : "text-emerald-600"} onClick={() => basculer(e)} /></td></tr>))}
            {!liste.length && <tr><td colSpan={7} className="text-slate-500">Aucune auto-école : créez la première.</td></tr>}</tbody></table>
      </div>
      {nouveau && <NouvelleEcole onFermer={() => setNouveau(false)} onFait={() => { setNouveau(false); charger(); }} />}
    </div>
  );
}
