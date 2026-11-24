// Compte Google dans « Mon compte » : lier ou retirer la connexion par Google. Aucun compte Google n'ouvre une session sans avoir été lié ici, une fois connecté.
// Retirer la liaison demande le mot de passe. Masqué tant que le serveur n'est pas configuré pour Google.
import { Check, Link2, Link2Off, X } from "lucide-react";
import { useEffect, useState } from "react";
import Bouton from "./Bouton.jsx";
import ChampMotDePasse from "./ChampMotDePasse.jsx";
import { Champ } from "./Champs.jsx";
import { api } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { ouvrirGoogle } from "../lib/google.js";

export default function GoogleCompte() {
  const { avecToast } = useApp();
  const [etat, setEtat] = useState(null);                 // { disponible, lie, email, lie_le }
  const [mdp, setMdp] = useState("");
  const [retrait, setRetrait] = useState(false);
  const relire = () => api("/auth/google/etat").then(setEtat).catch(() => setEtat({ disponible: false }));
  useEffect(() => { relire(); }, []);
  if (!etat?.disponible) return null;

  const lier = () => avecToast("Ouverture de Google", async () => { const r = await api("/auth/google/lier-url", { methode: "POST", corps: { cible: "web" } }); ouvrirGoogle(r.url); }, () => "Google s'ouvre");
  const retirer = async () => {
    await avecToast("Retrait de la liaison Google", () => api("/auth/google/delier", { methode: "POST", corps: { mot_de_passe: mdp } }), () => "Liaison Google retirée");
    setMdp(""); setRetrait(false); relire();
  };

  return (
    <div className="mt-4 rounded-2xl bg-white p-4 ring-1 ring-encre/5" data-testid="bloc-google">
      <h2 className="font-semibold mb-2 flex items-center gap-2"><Link2 size={18} />Compte Google</h2>
      {etat.lie ? (
        <>
          <p className="text-sm mb-2">Lié à <b>{etat.email}</b>. Vous pouvez vous connecter avec « Se connecter avec Google ».</p>
          {!retrait ? <Bouton icone={Link2Off} onClick={() => setRetrait(true)}>Retirer la liaison</Bouton> : (
            <div className="space-y-2">
              <Champ libelle="Mot de passe d'AutoÉcole Pro (pour confirmer)"><ChampMotDePasse valeur={mdp} onChange={setMdp} /></Champ>
              <div className="flex gap-2"><Bouton variante="principal" icone={Check} disabled={!mdp} onClick={retirer}>Confirmer</Bouton><Bouton icone={X} onClick={() => { setRetrait(false); setMdp(""); }}>Annuler</Bouton></div>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-ardoise mb-2">Liez votre compte Google pour vous connecter sans taper votre mot de passe. Google confirme votre identité ; AutoÉcole Pro ne reçoit jamais votre mot de passe Google.</p>
          <Bouton variante="principal" icone={Link2} onClick={lier}>Lier mon compte Google</Bouton>
        </>
      )}
    </div>
  );
}
