// Client de l'API : ajoute le jeton et l'auto-école de travail, transforme les erreurs en messages lisibles, déconnecte si la session a expiré.
// Tous les chemins s'écrivent SANS le préfixe « /api » (ajouté ici).
const BASE = (import.meta.env.VITE_API_URL || "") + "/api";
let surSessionExpiree = () => {};
export const definirSurSessionExpiree = (f) => { surSessionExpiree = f; };

export const jeton = {
  lire: () => { try { return sessionStorage.getItem("jeton") || ""; } catch { return ""; } },
  ecrire: (v) => { try { v ? sessionStorage.setItem("jeton", v) : sessionStorage.removeItem("jeton"); } catch { /* stockage indisponible */ } },
};

// Auto-école de travail choisie par le super administrateur de la plateforme : envoyée dans l'en-tête X-Ecole (le serveur l'ignore pour les autres comptes).
export const ecole = {
  lire: () => { try { return sessionStorage.getItem("ecole") || ""; } catch { return ""; } },
  ecrire: (v) => { try { v ? sessionStorage.setItem("ecole", v) : sessionStorage.removeItem("ecole"); } catch { /* stockage indisponible */ } },
};
export function entetesAuth() {
  const e = {};
  if (jeton.lire()) e.Authorization = "Bearer " + jeton.lire();
  if (ecole.lire()) e["X-Ecole"] = ecole.lire();
  return e;
}

/** Appel d'une route de l'API. Lève une Error dont le message est celui du serveur (en français). */
export async function api(chemin, { methode = "GET", corps, avecJeton = true } = {}) {
  const entetes = { "Content-Type": "application/json", ...(avecJeton ? entetesAuth() : {}) };
  let r;
  try {
    r = await fetch(BASE + chemin, { method: methode, headers: entetes, body: corps === undefined ? undefined : JSON.stringify(corps) });
  } catch {
    throw new Error("Serveur injoignable : vérifiez la connexion Internet");
  }
  let donnees = null;
  try { donnees = await r.json(); } catch { /* corps vide */ }
  if (!r.ok) {
    if (r.status === 401 && avecJeton) surSessionExpiree();
    const d = donnees?.detail;
    const e = new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join(" ; ") : "Erreur " + r.status);
    e.statut = r.status;
    throw e;
  }
  if (donnees === null) throw new Error("Réponse inattendue du serveur");
  return donnees;
}

/** Récupère un PDF protégé (jeton exigé) sous forme d'adresse « blob: » affichable dans le lecteur interne. */
export async function chargerPdf(chemin) {
  let r;
  try { r = await fetch(BASE + chemin, { headers: entetesAuth() }); } catch { throw new Error("Serveur injoignable : vérifiez la connexion Internet"); }
  if (!r.ok) throw new Error("Document indisponible (erreur " + r.status + ")");
  return URL.createObjectURL(await r.blob());
}
