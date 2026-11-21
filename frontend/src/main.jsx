import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { Fournisseur } from "./lib/contexte.jsx";
import "./index.css";
import { installerDefilementTableaux } from "./lib/defilementTableaux";   // règle 24 (18/11/2026) : tableaux de plus de 30 lignes

import { installerValidationFormulaires } from "./lib/validationFormulaires";   // champs obligatoires vides en fond rouge à la validation (21/11/2026)

installerDefilementTableaux();
installerValidationFormulaires();

createRoot(document.getElementById("racine")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Fournisseur>
        <App />
      </Fournisseur>
    </BrowserRouter>
  </React.StrictMode>,
);
