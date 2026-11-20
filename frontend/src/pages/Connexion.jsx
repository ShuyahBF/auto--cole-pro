// Page de connexion : carte centrée avec logo, état du serveur, version, œil sur le mot de passe.
import { LogIn, ServerCog, ServerCrash } from "lucide-react";
import { useEffect, useState } from "react";
import BandeauVersion from "../composants/BandeauVersion.jsx";
import Bouton from "../composants/Bouton.jsx";
import ChampMotDePasse from "../composants/ChampMotDePasse.jsx";
import { Champ, Texte } from "../composants/Champs.jsx";
import Logo from "../composants/Logo.jsx";
import { api, jeton } from "../lib/api.js";
import { useApp } from "../lib/contexte.jsx";

export default function Connexion() {
  const { setUtilisateur, toast, retirer } = useApp();
  const [login, setLogin] = useState("");
  const [mdp, setMdp] = useState("");
  const [attente, setAttente] = useState(false);
  const [etat, setEtat] = useState("verification");          // verification | actif | lent | injoignable

  // État du serveur : « Serveur actif », lent (> 3 s) ou injoignable.
  useEffect(() => {
    const debut = Date.now();
    api("/sante", { avecJeton: false })
      .then((s) => setEtat(s.base === "ok" ? (Date.now() - debut > 3000 ? "lent" : "actif") : "injoignable"))
      .catch(() => setEtat("injoignable"));
  }, []);

  /** Connexion avec toast « Patientez… » et jauge ; le message d'erreur est celui du serveur. */
  async function envoyer(e) {
    e.preventDefault();
    setAttente(true);
    const id = toast("Patientez… connexion en cours", "attente");
    try {
      const r = await api("/auth/login", { methode: "POST", avecJeton: false, corps: { login, mot_de_passe: mdp } });
      jeton.ecrire(r.jeton);
      setUtilisateur(await api("/me"));
    } catch (err) { toast(err.message, "erreur"); } finally { retirer(id); setAttente(false); }
  }

  const etats = {
    verification: { txt: "Vérification du serveur…", cl: "text-slate-500", Ic: ServerCog }, actif: { txt: "Serveur actif", cl: "text-emerald-700", Ic: ServerCog },
    lent: { txt: "Serveur lent à répondre", cl: "text-orange-700", Ic: ServerCog }, injoignable: { txt: "Serveur injoignable", cl: "text-rose-700", Ic: ServerCrash },
  }[etat];

  return (
    <div className="grid min-h-screen place-items-center bg-encre px-4 py-10">
      <main className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl sm:p-8">
        <div className="flex flex-col items-center">
          <Logo taille={40} />
          <h1 className="mt-5 text-center font-editorial text-2xl font-bold italic text-encre">Gestion des auto-écoles</h1>
          <p className="mt-1 text-sm text-ardoise">Espace réservé au personnel</p>
        </div>
        <form onSubmit={envoyer} className="mt-5">
          <Texte libelle="Identifiant" valeur={login} onChange={setLogin} autoComplete="username" placeholder="awa.badini@gmail.com" required />
          <Champ libelle="Mot de passe"><ChampMotDePasse valeur={mdp} onChange={setMdp} /></Champ>
          <Bouton type="submit" icone={LogIn} variante="principal" attente={attente} className="w-full">Se connecter</Bouton>
        </form>
        <p className={`mt-4 flex items-center justify-center gap-1.5 text-xs font-semibold ${etats.cl}`}><etats.Ic size={14} />{etats.txt}</p>
        <BandeauVersion className="mt-1 text-center" />
      </main>
    </div>
  );
}
