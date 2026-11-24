// google.js — connexion par compte Google, côté site AutoÉcole Pro. Déroulé complet : backend/app/google_auth.py.
import { api } from "./api.js";

const BASE = (import.meta.env.VITE_API_URL || "") + "/api";

/** Le serveur est-il configuré pour Google ? (le bouton n'est affiché que si oui) */
export const googleDisponible = () => api("/auth/google/config", { avecJeton: false }).then((r) => !!r.disponible).catch(() => false);

/** Adresse de départ de la connexion (le serveur renvoie ensuite vers Google). */
export const urlConnexionGoogle = () => `${BASE}/auth/google/demarrer?cible=web`;

/** Ouvre une adresse Google dans la même fenêtre. */
export function ouvrirGoogle(url) { window.location.href = url; return true; }

/** Messages clairs pour chaque cause d'échec renvoyée par le serveur (?erreur=…). */
export const MESSAGES_GOOGLE = {
  aucun_compte: "Aucun compte AutoÉcole Pro n'est lié à ce compte Google. Connectez-vous avec votre identifiant, puis liez Google dans « Mon compte ».",
  deja_lie: "Ce compte Google est déjà lié à un autre compte AutoÉcole Pro.",
  bloque: "Ce compte est désactivé : contactez la direction de l'auto-école.",
  refuse: "La connexion par Google a été annulée ou refusée.",
  google: "Google n'a pas pu confirmer votre identité (e-mail vérifié exigé). Réessayez.",
  etat: "Cette demande a expiré. Recommencez la connexion.",
};
