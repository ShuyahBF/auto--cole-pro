// Détection d'une nouvelle version du SITE (même principe que SAWALI et ALBARKA).
// À chaque déploiement, la compilation produit des fichiers dont le nom change (ex. /assets/index-guTt2EWU.js). La page ouverte garde les anciens noms ;
// si la page d'accueil téléchargée sans cache cite d'autres noms, une nouvelle version est en ligne et le site propose d'actualiser.

/** Noms des fichiers principaux (index-xxxx.js / .css) cités dans un texte HTML, triés et joints ; "" s'il n'y en a pas. */
export function empreinteHtml(html) {
  const trouves = String(html || "").match(/\/assets\/index-[A-Za-z0-9_-]+\.(?:js|css)/g) || [];
  return [...new Set(trouves)].sort().join("|");
}

/** Empreinte de la page actuellement ouverte : lit ses balises <script> et <link>. */
export function empreinteChargee(doc) {
  const morceaux = [];
  doc.querySelectorAll("script[src], link[rel='stylesheet'][href]").forEach((el) => morceaux.push(el.getAttribute("src") || el.getAttribute("href") || ""));
  return empreinteHtml(morceaux.join("\n"));
}

/** Vrai si une nouvelle version est en ligne : les deux empreintes existent et diffèrent. En développement (aucun fichier « index-<hash> ») : jamais. */
export const nouvelleVersionDisponible = (chargee, enLigne) => !!chargee && !!enLigne && chargee !== enLigne;
