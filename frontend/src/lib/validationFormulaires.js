// =============================================================================
// Champs obligatoires : contrôle à la validation d'une fiche (règle du propriétaire, 21/11/2026)
// =============================================================================
// « A la validation de la fiche, mettre les champs obligatoires manquants en fond rouge (champ de saisie). »
//
// Pour un développeur WinDev : un seul module installé au démarrage du site, comme les autres règles globales ; rien à ajouter fiche par fiche.
//  - Un champ est OBLIGATOIRE quand son intitulé se termine par « * » (composant Champ : l'étoile est collée au mot, « Nom* », et l'étiquette porte data-requis).
//  - Quand on appuie sur le bouton PRINCIPAL d'une fiche (bouton plein marqué data-principal, dans une fenêtre ou un formulaire),
//    les champs obligatoires VIDES passent en fond rouge, le premier reçoit le curseur, un message liste les champs manquants, et l'action n'est PAS lancée.
//  - Le rouge s'en va dès que la personne saisit ou choisit une valeur.
// =============================================================================

export const CLASSE_MANQUANT = "champ-manquant";

/** Zone de saisie (champ, liste, zone de texte) contenue dans l'étiquette d'un champ obligatoire ; null pour une case à cocher ou un champ caché. */
export function controleDe(etiquette) {
  return etiquette.querySelector("input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]), select, textarea");
}

/** Vrai si la valeur du contrôle est vide (espaces seuls compris). */
export function estVide(controle) {
  return String(controle.value ?? "").trim() === "";
}

/** Intitulé lisible d'une étiquette (sans l'étoile). */
function intitule(etiquette) {
  const t = etiquette.querySelector("[data-intitule]");
  return (t ? t.textContent : etiquette.textContent || "").replace(/\*/g, "").trim();
}

/** Marque en rouge les champs obligatoires vides de la zone ; rend la liste des intitulés manquants (vide = fiche complète). */
export function verifierZone(zone) {
  const manquants = [];
  let premier = null;
  zone.querySelectorAll("label[data-requis]").forEach((etiquette) => {
    const controle = controleDe(etiquette);
    if (!controle || controle.disabled) return;
    if (estVide(controle)) {
      controle.classList.add(CLASSE_MANQUANT);
      controle.setAttribute("aria-invalid", "true");
      manquants.push(intitule(etiquette));
      if (!premier) premier = controle;
    }
  });
  if (premier) premier.focus();
  return manquants;
}

/** Retire le rouge d'un champ dès qu'on y saisit quelque chose. */
function effacerSiRempli(e) {
  const c = e.target;
  if (c && c.classList && c.classList.contains(CLASSE_MANQUANT) && !estVide(c)) {
    c.classList.remove(CLASSE_MANQUANT);
    c.removeAttribute("aria-invalid");
  }
}

let installe = false;

/** Installe le contrôle (une seule fois, au démarrage du site). */
export function installerValidationFormulaires() {
  if (installe || typeof document === "undefined") return;
  installe = true;
  // Phase de capture : le contrôle passe AVANT l'action du bouton (qui n'est pas lancée si la fiche est incomplète)
  document.addEventListener("click", (e) => {
    const bouton = e.target.closest && e.target.closest("button[data-principal]");
    if (!bouton || bouton.disabled) return;
    const zone = bouton.closest("[role=dialog], form, [data-formulaire]");
    if (!zone) return;
    const manquants = verifierZone(zone);
    if (manquants.length) {
      e.preventDefault();
      e.stopPropagation();
      window.dispatchEvent(new CustomEvent("champs-manquants", { detail: { manquants } }));
    }
  }, true);
  document.addEventListener("input", effacerSiRempli, true);
  document.addEventListener("change", effacerSiRempli, true);
}
