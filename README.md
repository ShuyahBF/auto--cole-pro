# AutoÉcole Pro

Plateforme web de gestion d'auto-écoles (multi-écoles, multi-pays, paramétrable).

**Lot 1 (fondation)** : auto-écoles et agences, comptes et rôles, tarifs et promotions, inscriptions des élèves (dossier, pièces, échéancier, statuts), paiements et reçus PDF,
impayés, tableau de bord, journal d'audit.

**À venir** : examens internes et externes (sessions, convocations, résultats, plannings), transferts de dossiers, statistiques ; parc de véhicules (kilométrage, carburant, pannes,
interventions, pièces détachées, approvisionnement) ; centre de messagerie WhatsApp (Transmission universelle puis ligne privée) ; évaluations par les clients.

## Variables d'environnement (Render, saisies par le propriétaire)
`MONGODB_URI` (secret), `MONGODB_BASE`, `JWT_SECRET`, `SUPERADMIN_LOGIN`, `SUPERADMIN_MOT_DE_PASSE` (secret, à changer à la première connexion), `FRONTEND_ORIGIN`, `VITE_API_URL` (site).

## Développement
```bash
cd backend && pip install -r requirements-test.txt && python -m pytest tests -q
cd frontend && npm install && npm test && npm run build
```
