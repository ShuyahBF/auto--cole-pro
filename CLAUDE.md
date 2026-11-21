# AutoÉcole Pro — règles du dépôt (propriétaire ShuyahBF)

Les règles permanentes du propriétaire (voir le CLAUDE.md de `ShuyahBF/Aizenta-Analyse-Qualit-Gestion-Stocks` ou `ShuyahBF/Emergent`) s'appliquent ici :
commits au nom de `ShuyahBF` en français sans mention d'IA ni Co-Authored-By, commentaires clairs sur chaque bloc, aucun secret dans le dépôt, version et lot mis à jour
à chaque déploiement, compte rendu par e-mail HTML après chaque livraison, pictogramme + légende sur toute action, toasts « … en cours » puis résultat, tableaux triables
(survol bleu clair, sélection orange à police bleu nuit, nombres à droite, totaux sous les colonnes numériques, défilement au-delà de 30 lignes), listes finies en listes déroulantes,
détails en fenêtre modale (28 / 36 rem, 85 % de hauteur), œil sur toute saisie secrète, exemples « BADINI Awa » / « awa.badini@gmail.com », menus avec une majuscule à chaque mot,
pastilles de notifications dans le menu, présence déclarée à SAWALI, outils de maintenance en interface graphique (le propriétaire ne manipule ni Python ni PowerShell).

## Plateforme
- AutoÉcole Pro = gestion complète d'auto-écoles, **multi-écoles et multi-pays PARAMÉTRABLE** (décision du propriétaire, 20/11/2026) : pays, devise, catégories de permis, épreuves d'examen,
  pièces à fournir et modes de paiement sont réglés PAR auto-école (`backend/app/ecoles.py`) ; les valeurs par pays sont des points de départ à valider selon la réglementation locale.
- Dépôt `ShuyahBF/autoecole-pro`, branche de base `main`. `backend/` : FastAPI + MongoDB (mongomock en test) ; `frontend/` : React, Vite, Tailwind, lucide-react. Render : `render.yaml` (`autoecole-pro-api`, `autoecole-pro-web`).
- Version : source unique `backend/lot.py` (VERSION `1.N` +1 et LOT = numéro de la PR fusionnée à chaque déploiement), exposée par `/api/version`. Connexion et portail : « Version X · déployée le JJ/MM/AAAA HH:MM ».

## Architecture multi-écoles (modèle Dialyse)
- Une auto-école = un « locataire ». Toute donnée de travail porte `ecole_id` ; `db.base()` renvoie la vue de l'école courante (collections de `COLLECTIONS_ECOLE` filtrées automatiquement, marquées à l'écriture,
  erreur 400 sans école : jamais « tout »). `db.brut()` (sans filtre) est réservé aux listes d'écoles, comptes et journal : toute nouvelle utilisation doit avoir une raison écrite.
  Toute NOUVELLE collection de données d'école est ajoutée à `COLLECTIONS_ECOLE`.
- Un compte rattaché à une école travaille TOUJOURS dans la sienne (`X-Ecole` ignoré). Le super administrateur de la plateforme (sans école) choisit l'école par `X-Ecole`.
- Un compte limité à une agence (`agence_id`) ne voit que son agence. Le moniteur ne voit AUCUN montant : le serveur retire les champs financiers (pas l'écran).

## Décisions du lot 1 (fondation)
- Montants dans la devise de l'école, arrondis à ses décimales (`tarifs.arrondi`) ; la devise ne change plus après le premier paiement.
- Prix, remise et net sont COPIÉS du tarif à l'inscription (un tarif modifié ne change pas un dossier) ; un tarif utilisé se désactive, il ne se supprime pas.
- Matricule `PRÉFIXE-AA-000001` (compteur atomique par école et par année), âge minimum de la catégorie contrôlé, doublon (nom + prénom + naissance) refusé sauf confirmation.
- Paiements : jamais au-delà du reste dû, référence obligatoire hors espèces, reçu `R-AAAA-000001`, annulation motivée (jamais de suppression, numéro jamais réutilisé), reçu PDF servi en ligne.
- Impayés : retard = échéances dépassées non couvertes par les paiements. Pastilles du menu : `GET /api/notifications/compteurs` (dossiers incomplets, impayés en retard).

## Tests avant toute livraison
- `cd backend && python -m pytest tests -q` (base en mémoire `mongomock`).
- `cd frontend && npm test && npm run build`.

## Lot 2 : examens, transferts, livret (20/11/2026)
- L'ORDRE des épreuves des paramètres de l'école fixe la progression (une épreuve exige d'avoir été ADMIS à la précédente, même catégorie) ; admis à la dernière = « Permis obtenu ».
- Éligibilité à une session (`examens.controle_eligibilite`, refaite par le serveur) : élève actif, même catégorie, dossier complet, pas d'impayé en RETARD (un responsable peut `forcer` pour un examen INTERNE seulement), pas déjà inscrit, places.
- Convocation PDF (A5), liste de présence PDF (A4), planning du mois, statistiques (`/statistiques/examens` : taux de réussite sans compter les absents, tentatives, délai jusqu'au permis).
- Transferts : entre agences (responsables), sortant (reste dû = confirmation du solde, dossier PDF, élève « Transféré »), entrant (inscription + école d'origine + heures reprises au livret). Rien n'est supprimé.
- Livret de progression (`seances.py`) : séances de conduite / code consignées par le moniteur (durée 15-480 min), heures effectuées vs prévues ; seuls les responsables corrigent.

## Lot 3 : parc automobile (20/11/2026)
- Le kilométrage ne recule JAMAIS (relevé, plein) ; seul un responsable corrige avec motif. Consommation = entre deux pleins COMPLETS, anomalie au-delà de 40 % de la moyenne du véhicule.
- Panne « immobilisante » → véhicule « en panne » ; libéré quand plus aucune panne immobilisante n'est ouverte. Intervention terminée : pièces décomptées du stock (409 si insuffisant, rien décompté), coût = main-d'œuvre + pièces, panne liée résolue, prochain entretien.
- Les MONTANTS du parc ne sont vus que par `COUTS_PARC` (comptable, mécanicien, responsables) : le serveur les retire (`parc._masquer`). Moniteur et secrétariat : aucun montant.
- Alertes (`parc.calculer_alertes`) : documents expirés / à 30 jours, entretien dû, pannes ouvertes, pièces sous le seuil, consommation anormale ; pastille « Parc automobile » = alertes rouges. Stock jamais négatif, commandes brouillon → commandée → reçue (la réception crée les entrées de stock et met à jour le prix).

## Lot 4 : messagerie WhatsApp et évaluations (20/11/2026)
- WhatsApp par la Transmission universelle (Liluvine) de SAWALI : `backend/app/whatsapp.py` (protocole signé HMAC, émetteur par défaut « autoecole »). Variables Render : `LILUVINE_WA_URL`, `LILUVINE_WA_HMAC` (SECRET), `LILUVINE_WA_EMETTEUR`, `FRONTEND_ORIGIN`.
- LIGNE PRIVÉE d'une école : fiche école (`wa_emetteur`, `wa_repli`, réglés par le super administrateur via `PUT /api/messagerie/ligne`) + variable Render `LILUVINE_WA_HMAC_<PRÉFIXE>` ; sans elle l'école reste sur la ligne partagée, sans changer le code.
- ADRESSE DE RETOUR de SAWALI (règle 7) : `POST /api/webhooks/liluvine-retour` (signée, 5 min) : `stats_du_jour`, `statut`, `reponse` (« 1 / 2 » confirment ou excusent l'examen), `desinscription` (STOP). À saisir dans SAWALI : émetteur « autoecole » → « URL de retour » = `https://<serveur AutoÉcole Pro>/api/webhooks/liluvine-retour` (« URL des statistiques » vide).
- Aucun montant ni donnée de santé par WhatsApp ; le texte d'un message n'est jamais journalisé ; envoi toujours en arrière-plan.
- Évaluations : lien personnel à usage unique (seule l'empreinte SHA-256 du jeton est gardée, 30 jours), page publique `/avis/<jeton>` sans compte, satisfaction 1-5, NPS 0-10, critères, publication seulement si le client l'a autorisée ; le moniteur évalué est déduit du livret.

## Règles de saisie des fiches (propriétaire, 21/11/2026 : « comme règle générale », valables pour TOUTES les plateformes)
- **Intitulés des entités en MAJUSCULES** : le nom de l'entité créée selon la plateforme (ici le nom de l'auto-école et celui de l'agence ; pour e-Kol le nom de l'école, etc.) est saisi et enregistré en MAJUSCULES, accents gardés.
  Écran : `<Texte majuscules …>` (`composants/Champs.jsx`) ; serveur : `validation.texte(…, majuscules=True)` (le serveur ne se fie pas à l'écran). Test : `test_intitules_des_entites_toujours_en_majuscules`.
- **Champs obligatoires marqués d'une étoile collée à l'intitulé** : « Nom* » (jamais « Nom * » ni « Nom (obligatoire) »). Il suffit de finir le libellé par `*` : `Champ` colle l'étoile (rouge) et prévient les lecteurs d'écran.
- **Fiche incomplète = champs manquants en fond rouge** : module global `lib/validationFormulaires.js` (installé dans `main.jsx`, rien à ajouter fiche par fiche). Au clic sur le bouton principal d'une fenêtre ou d'un formulaire
  (`Bouton variante="principal"` porte `data-principal`), les champs obligatoires vides passent en fond rouge (`.champ-manquant`), le premier reçoit le curseur, un toast liste les champs manquants et l'action n'est PAS lancée ; le rouge disparaît à la saisie.
  Le serveur refait toujours le contrôle. Vérifié dans un vrai navigateur (fenêtre « Nouvelle auto-école »).
