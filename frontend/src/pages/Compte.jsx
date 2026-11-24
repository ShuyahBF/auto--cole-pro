// Mon compte : changement du mot de passe (œil + critères visibles pendant la saisie).
import { Save } from "lucide-react";
import { useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import ChampMotDePasse from "../composants/ChampMotDePasse.jsx";
import GoogleCompte from "../composants/GoogleCompte.jsx";
import ForceMotDePasse from "../composants/ForceMotDePasse.jsx";
import { Champ } from "../composants/Champs.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { motDePasseAssezFort } from "../lib/motdepasse.js";

export default function Compte({ obligatoire = false }) {
  const { utilisateur, setUtilisateur, avecToast } = useApp();
  const [ancien, setAncien] = useState("");
  const [nouveau, setNouveau] = useState("");
  const go = () => avecToast("Changement du mot de passe", () => api("/auth/changer-mot-de-passe", { methode: "POST", corps: { ancien, nouveau } }), () => "Mot de passe changé")
    .then(() => { setAncien(""); setNouveau(""); setUtilisateur({ ...utilisateur, doit_changer_mdp: false }); }).catch(() => {});
  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-2xl font-bold">Mon compte</h1>
      <p className="mb-4 text-sm text-ardoise">{utilisateur.nom} · {utilisateur.role_libelle}{obligatoire && " — vous devez choisir un nouveau mot de passe pour continuer."}</p>
      <div className="rounded-2xl bg-white p-4 ring-1 ring-encre/5">
        <Champ libelle="Ancien mot de passe"><ChampMotDePasse valeur={ancien} onChange={setAncien} /></Champ>
        <Champ libelle="Nouveau mot de passe"><ChampMotDePasse valeur={nouveau} onChange={setNouveau} autoComplete="new-password" /></Champ><ForceMotDePasse valeur={nouveau} />
        <Bouton icone={Save} variante="principal" disabled={!ancien || !motDePasseAssezFort(nouveau)} onClick={go}>Changer le mot de passe</Bouton>
      </div>
      {!obligatoire && <GoogleCompte />}
    </div>
  );
}
