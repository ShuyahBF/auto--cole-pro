// Routes : connexion si non connecté ; changement de mot de passe obligatoire après réinitialisation.
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import MiseEnPage from "./composants/MiseEnPage.jsx";
import Toasts from "./composants/Toasts.jsx";
import { useApp } from "./lib/contexte.jsx";
import Caisse from "./pages/Caisse.jsx";
import Compte from "./pages/Compte.jsx";
import Comptes from "./pages/Comptes.jsx";
import Connexion from "./pages/Connexion.jsx";
import Ecoles from "./pages/Ecoles.jsx";
import Eleves from "./pages/Eleves.jsx";
import Impayes from "./pages/Impayes.jsx";
import Journal from "./pages/Journal.jsx";
import Parametres from "./pages/Parametres.jsx";
import Examens from "./pages/Examens.jsx";
import Statistiques from "./pages/Statistiques.jsx";
import Transferts from "./pages/Transferts.jsx";
import Parc from "./pages/Parc.jsx";
import Pieces from "./pages/Pieces.jsx";
import Avis from "./pages/Avis.jsx";
import AvisPublic from "./pages/AvisPublic.jsx";
import Messagerie from "./pages/Messagerie.jsx";
import Tableau from "./pages/Tableau.jsx";
import Tarifs from "./pages/Tarifs.jsx";

export default function App() {
  const { utilisateur, pret } = useApp();
  const { pathname } = useLocation();
  // Page PUBLIQUE d'évaluation (lien reçu par WhatsApp) : accessible sans compte, hors du portail.
  if (pathname.startsWith("/avis/")) return <Routes><Route path="avis/:jeton" element={<AvisPublic />} /></Routes>;
  if (!pret) return <div className="min-h-dvh flex items-center justify-center"><span className="jauge" /></div>;
  const role = utilisateur?.role;
  const accueil = role === "mecanicien" ? "/parc" : ["super_admin", "directeur", "gestionnaire", "comptable"].includes(role) ? "/" : "/eleves";
  return (
    <>
      {!utilisateur ? <Connexion /> : utilisateur.doit_changer_mdp ? <div className="min-h-dvh p-6"><Compte obligatoire /></div> : (
        <Routes>
          <Route element={<MiseEnPage />}>
            <Route index element={accueil === "/" ? <Tableau /> : <Navigate to={accueil} replace />} />
            <Route path="eleves" element={<Eleves />} />
            <Route path="examens" element={<Examens />} />
            <Route path="transferts" element={<Transferts />} />
            <Route path="statistiques" element={<Statistiques />} />
            <Route path="parc" element={<Parc />} />
            <Route path="pieces" element={<Pieces />} />
            <Route path="messagerie" element={<Messagerie />} />
            <Route path="avis" element={<Avis />} />
            <Route path="caisse" element={<Caisse />} />
            <Route path="impayes" element={<Impayes />} />
            <Route path="tarifs" element={<Tarifs />} />
            <Route path="ecoles" element={<Ecoles />} />
            <Route path="parametres" element={<Parametres />} />
            <Route path="comptes" element={<Comptes />} />
            <Route path="journal" element={<Journal />} />
            <Route path="compte" element={<Compte />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>)}
      <Toasts />
    </>
  );
}
