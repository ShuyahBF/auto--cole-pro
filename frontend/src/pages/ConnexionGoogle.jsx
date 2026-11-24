// Page d'arrivée après Google : « /connexion-google?code=… » (ou ?erreur=…, ?lie=1). Le code à usage unique est échangé contre le jeton.
import { LogIn } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Bouton from "../composants/Bouton.jsx";
import { api, jeton } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";
import { MESSAGES_GOOGLE } from "../lib/google.js";

export default function ConnexionGoogle() {
  const { setUtilisateur, toast } = useApp();
  const naviguer = useNavigate();
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code"), echec = params.get("erreur"), lie = params.get("lie");
  const [erreur, setErreur] = useState("");
  const fait = useRef(false);                           // un seul échange, même si React redessine la page

  useEffect(() => {
    if (fait.current) return;
    fait.current = true;
    if (lie) { toast("Compte Google lié : vous pouvez maintenant vous connecter avec Google.", "ok"); naviguer("/compte", { replace: true }); return; }
    if (echec || !code) { setErreur(MESSAGES_GOOGLE[echec] || "Connexion par Google impossible."); return; }
    api("/auth/google/echange", { methode: "POST", avecJeton: false, corps: { code } })
      .then(async (r) => { jeton.ecrire(r.jeton); setUtilisateur(await api("/me")); naviguer("/", { replace: true }); })
      .catch((err) => setErreur(err.message));
  }, []);                                               // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="grid min-h-screen place-items-center bg-encre px-4 py-10">
      <main className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl space-y-3 text-center" data-testid="connexion-google">
        {erreur ? (
          <>
            <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900">{erreur}</p>
            <Bouton icone={LogIn} variante="principal" className="w-full" onClick={() => naviguer("/", { replace: true })}>Retour à la connexion</Bouton>
          </>
        ) : <p className="text-sm text-ardoise">Patientez… connexion par Google en cours.</p>}
      </main>
    </div>
  );
}
