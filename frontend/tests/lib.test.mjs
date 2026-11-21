// Tests des fonctions pures du site : tri (vides en dernier, sans accents), montants, libellés de menu.
import assert from "node:assert/strict";
import { trierLignes } from "../src/lib/tri.js";
import { montant, titreMenu, dateFr } from "../src/lib/format.js";
import { criteresMotDePasse } from "../src/lib/motdepasse.js";
import { empreinteHtml, nouvelleVersionDisponible } from "../src/lib/versionSite.js";

const l = [{ n: "Élodie" }, { n: "" }, { n: "adama" }, { n: "Zoé" }];
assert.deepEqual(trierLignes(l, "n", 1).map((x) => x.n), ["adama", "Élodie", "Zoé", ""]);       // sans accents ni casse, vide en dernier
assert.deepEqual(trierLignes(l, "n", -1).map((x) => x.n), ["Zoé", "Élodie", "adama", ""]);      // vide toujours en dernier
assert.equal(trierLignes(l, "n", 0), l);                                                         // sens 0 = ordre d'origine
assert.deepEqual(trierLignes([{ v: 10 }, { v: 9 }], "v", 1).map((x) => x.v), [9, 10]);           // nombres numériquement
assert.equal(montant(150000, "FCFA", 0), "150 000 FCFA");
assert.equal(montant(12.5, "EUR", 2), "12,50 EUR");
assert.equal(titreMenu("caisse et paiements"), "Caisse Et Paiements");
assert.equal(dateFr("2026-11-20"), "20/11/2026");
assert.ok(criteresMotDePasse("Motdepasse9").every((c) => c.ok));
console.log("tests du site : ok");

// Nouvelle version du site : comparaison des fichiers principaux de la page ouverte et de la page en ligne
const ancienne = '<script src="/assets/index-AAA111.js"></script><link href="/assets/index-BBB222.css">';
const nouvelle = '<script src="/assets/index-CCC333.js"></script><link href="/assets/index-BBB222.css">';
assert.equal(nouvelleVersionDisponible(empreinteHtml(ancienne), empreinteHtml(ancienne)), false);   // même version : pas de bandeau
assert.equal(nouvelleVersionDisponible(empreinteHtml(ancienne), empreinteHtml(nouvelle)), true);    // fichiers différents : bandeau
assert.equal(nouvelleVersionDisponible("", empreinteHtml(nouvelle)), false);                         // développement : jamais
