// Contexte global : utilisateur connecté, version du serveur, toasts (« … en cours » puis résultat), auto-école de travail et pastilles du menu.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, definirSurSessionExpiree, ecole as ecoleStock, jeton } from "./api.js";

const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function Fournisseur({ children }) {
  const [utilisateur, setUtilisateur] = useState(null);
  const [pret, setPret] = useState(false);
  const [version, setVersion] = useState(null);
  const [toasts, setToasts] = useState([]);
  // Auto-écoles visibles et école de travail (le super administrateur de la plateforme choisit ; les autres ont la leur, imposée par le serveur).
  const [ecoles, setEcoles] = useState([]);
  const [ecoleChoisie, setEcoleChoisie] = useState(ecoleStock.lire());
  const [parametres, setParametres] = useState(null);           // paramétrage de l'école de travail (devise, catégories, pièces, modes de paiement…)
  const [compteurs, setCompteurs] = useState({});               // pastilles du menu, relues toutes les 30 s
  const rafraichirCompteurs = useCallback(() => api("/notifications/compteurs").then(setCompteurs).catch(() => {}), []);
  const choisirEcole = useCallback((id) => { ecoleStock.ecrire(id || ""); setEcoleChoisie(id || ""); }, []);
  const rechargerParametres = useCallback(() => api("/ecole").then(setParametres).catch(() => setParametres(null)), []);
  const rechargerEcoles = useCallback(() => api("/ecoles").then(setEcoles), []);

  /** Affiche un toast (info | ok | erreur | attente). Les toasts « attente » restent jusqu'à retrait. */
  const toast = useCallback((message, type = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }].slice(-3));
    if (type !== "attente") setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), type === "erreur" ? 7000 : 3500);
    return id;
  }, []);
  const retirer = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  // Fiche incomplète (lib/validationFormulaires.js) : message listant les champs obligatoires manquants (champs en fond rouge)
  useEffect(() => {
    const surManquants = (e) => toast(`Champs obligatoires à renseigner : ${e.detail.manquants.join(", ")}`, "erreur");
    window.addEventListener("champs-manquants", surManquants);
    return () => window.removeEventListener("champs-manquants", surManquants);
  }, [toast]);

  /** Action asynchrone avec toast « … en cours » puis résultat (règle 17 : jamais d'actualisation silencieuse). */
  const avecToast = useCallback(async (enCours, action, resultat) => {
    const id = toast(enCours + " en cours…", "attente");
    try {
      const v = await action();
      retirer(id);
      toast(resultat ? resultat(v) : "Terminé", "ok");
      return v;
    } catch (e) {
      retirer(id);
      toast(e.message, "erreur");
      throw e;
    }
  }, [toast, retirer]);

  const deconnecter = useCallback(() => { jeton.ecrire(""); ecoleStock.ecrire(""); setEcoleChoisie(""); setEcoles([]); setParametres(null); setUtilisateur(null); }, []);

  // Après connexion : liste des écoles ; le super administrateur sans choix valide reprend la seule école existante.
  useEffect(() => {
    if (!utilisateur) return;
    api("/ecoles").then((l) => {
      setEcoles(l);
      if (utilisateur.plateforme && !l.some((c) => c.id === ecoleStock.lire())) choisirEcole(l.length === 1 ? l[0].id : "");
    }).catch(() => {});
  }, [utilisateur, choisirEcole]);

  // Paramétrage de l'école de travail (relu à chaque changement d'école).
  useEffect(() => {
    if (!utilisateur) return;
    if (utilisateur.plateforme && !ecoleChoisie) { setParametres(null); return; }
    rechargerParametres();
  }, [utilisateur, ecoleChoisie, rechargerParametres]);

  useEffect(() => {
    definirSurSessionExpiree(() => { deconnecter(); toast("Session expirée, reconnectez-vous", "erreur"); });
    api("/version", { avecJeton: false }).then(setVersion).catch(() => {});
    if (jeton.lire()) api("/me").then(setUtilisateur).catch(() => jeton.ecrire("")).finally(() => setPret(true));
    else setPret(true);
  }, [deconnecter, toast]);

  useEffect(() => {
    if (!utilisateur) { setCompteurs({}); return undefined; }
    if (utilisateur.plateforme && !ecoleChoisie) return undefined;
    rafraichirCompteurs();
    const t = setInterval(rafraichirCompteurs, 30000);
    return () => clearInterval(t);
  }, [utilisateur, ecoleChoisie, rafraichirCompteurs]);

  const valeur = useMemo(() => ({ utilisateur, setUtilisateur, pret, version, toast, retirer, avecToast, deconnecter, toasts, ecoles, ecoleChoisie, choisirEcole, rechargerEcoles, parametres, rechargerParametres, compteurs, rafraichirCompteurs }),
    [utilisateur, pret, version, toast, retirer, avecToast, deconnecter, toasts, ecoles, ecoleChoisie, choisirEcole, rechargerEcoles, parametres, rechargerParametres, compteurs, rafraichirCompteurs]);
  return <Ctx.Provider value={valeur}>{children}</Ctx.Provider>;
}

/** Formulaire avec détection des modifications (bouton Enregistrer actif seulement si changé : règle 15). */
export function useFormulaire(initial) {
  const [valeurs, setValeurs] = useState(initial);
  const [origine, setOrigine] = useState(initial);
  const maj = (cle, v) => setValeurs((x) => ({ ...x, [cle]: v }));
  const modifie = JSON.stringify(valeurs) !== JSON.stringify(origine);
  const reinitialiser = (nouveau) => { setValeurs(nouveau); setOrigine(nouveau); };
  return { valeurs, maj, setValeurs, modifie, reinitialiser };
}
