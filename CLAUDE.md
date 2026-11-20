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
