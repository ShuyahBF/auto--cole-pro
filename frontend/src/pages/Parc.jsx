// Parc automobile : véhicules, alertes (documents, entretien, pannes, stock, consommation), pannes, interventions, coûts.
// Détail d'un véhicule en FENÊTRE MODALE (règle 20) : kilométrage, carburant, pannes, interventions. Totaux sous les tableaux (règle 25).
import { AlertTriangle, Fuel, Gauge, Play, Plus, RefreshCw, Save, Wrench, CheckCircle2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Case, Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { aujourdhui, dateFr, montant } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

const STATUT = { en_service: ["En service", "vert"], en_panne: ["En panne", "rouge"], en_maintenance: ["En maintenance", "orange"], reforme: ["Réformé", "gris"] };
const TYPES = [["voiture", "Voiture"], ["moto", "Moto"], ["camion", "Poids lourd"], ["bus", "Autocar"], ["remorque", "Remorque"]].map(([valeur, libelle]) => ({ valeur, libelle }));
const CARBURANTS = [["essence", "Essence"], ["diesel", "Gasoil"], ["hybride", "Hybride"], ["electrique", "Électrique"], ["gpl", "GPL"]].map(([valeur, libelle]) => ({ valeur, libelle }));
const ECHEANCES = [["assurance_expire", "Assurance"], ["visite_expire", "Visite technique"], ["taxe_expire", "Vignette / taxe"], ["carte_grise_expire", "Carte grise"]];

function NouveauVehicule({ onFermer, onFait }) {
  const { avecToast } = useApp();
  const f = useFormulaire({ immatriculation: "", marque: "", modele: "", annee: "", type: "voiture", carburant: "essence", categorie_permis: "B", km_actuel: 0, intervalle_entretien_km: 10000, assurance_expire: "", visite_expire: "", taxe_expire: "", carte_grise_expire: "" });
  const v = f.valeurs;
  const enregistrer = () => avecToast("Création du véhicule", () => api("/parc/vehicules", { methode: "POST", corps: v }), () => "Véhicule créé").then(onFait).catch(() => {});
  return (
    <Modal titre="Nouveau véhicule" large onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!v.immatriculation || !v.marque || !v.modele} onClick={enregistrer}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <div className="grid gap-x-3 sm:grid-cols-3">
        <Texte libelle="Immatriculation *" majuscules valeur={v.immatriculation} onChange={(x) => f.maj("immatriculation", x)} placeholder="11 AA 1111" /><Texte libelle="Marque *" valeur={v.marque} onChange={(x) => f.maj("marque", x)} /><Texte libelle="Modèle *" valeur={v.modele} onChange={(x) => f.maj("modele", x)} />
        <Texte libelle="Année" type="number" valeur={v.annee} onChange={(x) => f.maj("annee", x)} /><Liste libelle="Type" valeur={v.type} onChange={(x) => f.maj("type", x)} vide={null} options={TYPES} /><Liste libelle="Carburant" valeur={v.carburant} onChange={(x) => f.maj("carburant", x)} vide={null} options={CARBURANTS} />
        <Texte libelle="Catégorie de permis préparée" valeur={v.categorie_permis} onChange={(x) => f.maj("categorie_permis", x)} /><Texte libelle="Kilométrage actuel" type="number" valeur={v.km_actuel} onChange={(x) => f.maj("km_actuel", x)} min="0" /><Texte libelle="Entretien tous les (km)" type="number" valeur={v.intervalle_entretien_km} onChange={(x) => f.maj("intervalle_entretien_km", x)} />
        {ECHEANCES.map(([k, l]) => <Texte key={k} libelle={`${l} : expire le`} type="date" valeur={v[k]} onChange={(x) => f.maj(k, x)} />)}
      </div>
    </Modal>
  );
}

function Vehicule({ id, onFermer, onChange }) {
  const { parametres, avecToast, utilisateur, toast } = useApp();
  const [v, setV] = useState(null);
  const [pl, setPl] = useState(null);
  const [kms, setKms] = useState([]);
  const [ints, setInts] = useState([]);
  const [km, setKm] = useState("");
  const [plein, setPlein] = useState({ litres: "", km: "", montant: "", station: "", plein_complet: true });
  const [panne, setPanne] = useState({ description: "", gravite: "mineure" });
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => {
    api("/parc/vehicules").then((l) => setV(l.find((x) => x.id === id)));
    api(`/parc/vehicules/${id}/pleins`).then(setPl); api(`/parc/vehicules/${id}/km`).then(setKms); api(`/parc/interventions?vehicule_id=${id}`).then(setInts);
  }, [id]);
  useEffect(() => { charger(); }, [charger]);
  if (!v) return <Modal titre="Véhicule" onFermer={onFermer}><div className="py-8 flex justify-center"><span className="jauge" /></div></Modal>;
  const couts = pl?.pleins?.[0] && "montant" in pl.pleins[0];
  const go = (nom, action, ok) => avecToast(nom, action, () => ok).then(() => { charger(); onChange(); }).catch(() => {});
  const peutGerer = ["mecanicien", "gestionnaire", "directeur", "super_admin"].includes(utilisateur.role);
  return (
    <Modal titre={`${v.marque} ${v.modele} — ${v.immatriculation}`} large onFermer={onFermer} pied={<Bouton onClick={onFermer}>Fermer</Bouton>}>
      <div className="flex flex-wrap items-center gap-2 text-sm"><Pastille couleur={STATUT[v.statut][1]}>{STATUT[v.statut][0]}</Pastille><span className="font-bold tabular-nums">{v.km_actuel.toLocaleString("fr-FR")} km</span>
        {pl?.conso_moyenne && <span>· {pl.conso_moyenne} L/100 km en moyenne</span>}{v.echeances_proches.map((e) => <Pastille key={e} couleur="orange" icone={AlertTriangle}>{e} à renouveler</Pastille>)}</div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <section className="rounded-2xl bg-brume p-3"><p className="flex items-center gap-1 text-sm font-semibold"><Gauge size={16} />Relever le kilométrage</p>
          <Texte libelle="Compteur (km)" type="number" valeur={km} onChange={setKm} min="0" /><Bouton icone={Save} variante="vert" petit disabled={!km} onClick={() => go("Enregistrement du relevé", () => api(`/parc/vehicules/${id}/km`, { methode: "POST", corps: { km } }).then(() => setKm("")), "Relevé enregistré")}>Enregistrer</Bouton></section>
        <section className="rounded-2xl bg-brume p-3"><p className="flex items-center gap-1 text-sm font-semibold"><AlertTriangle size={16} />Signaler une panne</p>
          <Texte libelle="Description" valeur={panne.description} onChange={(x) => setPanne({ ...panne, description: x })} /><Liste libelle="Gravité" valeur={panne.gravite} onChange={(x) => setPanne({ ...panne, gravite: x })} vide={null} options={[{ valeur: "mineure", libelle: "Mineure" }, { valeur: "majeure", libelle: "Majeure" }, { valeur: "immobilisante", libelle: "Immobilisante (véhicule à l'arrêt)" }]} />
          <Bouton icone={Save} variante="orange" petit disabled={!panne.description} onClick={() => go("Signalement de la panne", () => api(`/parc/vehicules/${id}/pannes`, { methode: "POST", corps: panne }).then(() => setPanne({ ...panne, description: "" })), "Panne signalée")}>Signaler</Bouton></section>
      </div>
      <section className="mt-3 rounded-2xl bg-brume p-3"><p className="flex items-center gap-1 text-sm font-semibold"><Fuel size={16} />Approvisionnement en carburant</p>
        <div className="grid gap-x-2 sm:grid-cols-4"><Texte libelle="Litres" type="number" valeur={plein.litres} onChange={(x) => setPlein({ ...plein, litres: x })} /><Texte libelle="Compteur (km)" type="number" valeur={plein.km} onChange={(x) => setPlein({ ...plein, km: x })} />
          <Texte libelle="Montant" type="number" valeur={plein.montant} onChange={(x) => setPlein({ ...plein, montant: x })} /><Texte libelle="Station" valeur={plein.station} onChange={(x) => setPlein({ ...plein, station: x })} /></div>
        <Case libelle="Plein complet (nécessaire au calcul de la consommation)" valeur={plein.plein_complet} onChange={(x) => setPlein({ ...plein, plein_complet: x })} />
        <Bouton icone={Save} variante="vert" petit disabled={!plein.litres || !plein.km} onClick={() => go("Enregistrement du plein", () => api(`/parc/vehicules/${id}/pleins`, { methode: "POST", corps: plein }).then(() => setPlein({ litres: "", km: "", montant: "", station: "", plein_complet: true })), "Plein enregistré")}>Enregistrer le plein</Bouton></section>
      {pl?.pleins?.length > 0 && <table className="tableau mt-3"><thead><tr><th>Date</th><th className="num">Km</th><th className="num">Litres</th>{couts && <th className="num">Montant</th>}<th className="num">L/100 km</th></tr></thead>
        <tbody>{pl.pleins.slice(0, 10).map((p) => <tr key={p.id}><td>{dateFr(p.date)}</td><td className="num">{p.km.toLocaleString("fr-FR")}</td><td className="num">{p.litres}</td>{couts && <td className="num">{m(p.montant)}</td>}<td className="num">{p.conso_100km ?? "—"} {p.anomalie && <Pastille couleur="orange" icone={AlertTriangle}>Anormale</Pastille>}</td></tr>)}</tbody>
        <tfoot><tr className="font-bold bg-brume"><td>{pl.pleins.length} plein(s)</td><td /><td className="num">{pl.litres_total}</td>{couts && <td className="num">{m(pl.pleins.reduce((a, p) => a + (p.montant || 0), 0))}</td>}<td /></tr></tfoot></table>}
      {ints.length > 0 && <><h3 className="mt-3 text-sm font-semibold">Interventions</h3><ul className="mt-1 space-y-1 text-sm">{ints.slice(0, 8).map((i) => <li key={i.id} className="flex flex-wrap items-center gap-2">{dateFr(i.date)} · {i.description} <Pastille couleur={{ planifiee: "bleu", en_cours: "orange", terminee: "vert", annulee: "gris" }[i.statut]}>{{ planifiee: "Planifiée", en_cours: "En cours", terminee: "Terminée", annulee: "Annulée" }[i.statut]}</Pastille>{i.cout_total != null && <b className="tabular-nums">{m(i.cout_total)}</b>}</li>)}</ul></>}
      {peutGerer && <p className="mt-3 text-xs text-ardoise">Les interventions se planifient et se terminent depuis l'onglet « Interventions » du parc.</p>}
      {kms.length > 0 && <p className="mt-2 text-xs text-slate-500">{kms.length} relevé(s) de kilométrage enregistré(s).</p>}
    </Modal>
  );
}

function Intervention({ onFermer, onFait, vehicules }) {
  const { avecToast } = useApp();
  const [pieces, setPieces] = useState([]);
  const f = useFormulaire({ vehicule_id: "", type: "entretien", description: "", date: aujourdhui(), prestataire: "", piece_id: "", quantite: 1 });
  useEffect(() => { api("/parc/pieces").then(setPieces); }, []);
  const v = f.valeurs;
  const enregistrer = () => avecToast("Création de l'intervention", () => api(`/parc/vehicules/${v.vehicule_id}/interventions`, { methode: "POST", corps: { ...v, pieces: v.piece_id ? [{ piece_id: v.piece_id, quantite: v.quantite }] : [] } }), () => "Intervention planifiée").then(onFait).catch(() => {});
  return (
    <Modal titre="Planifier une intervention" onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!v.vehicule_id || !v.description} onClick={enregistrer}>Planifier</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Liste libelle="Véhicule *" valeur={v.vehicule_id} onChange={(x) => f.maj("vehicule_id", x)} options={vehicules.map((x) => ({ valeur: x.id, libelle: `${x.immatriculation} — ${x.marque} ${x.modele}` }))} />
      <div className="grid grid-cols-2 gap-x-3"><Liste libelle="Type" valeur={v.type} onChange={(x) => f.maj("type", x)} vide={null} options={[{ valeur: "entretien", libelle: "Entretien" }, { valeur: "reparation", libelle: "Réparation" }, { valeur: "controle", libelle: "Contrôle / visite" }, { valeur: "autre", libelle: "Autre" }]} /><Texte libelle="Date prévue" type="date" valeur={v.date} onChange={(x) => f.maj("date", x)} /></div>
      <Texte libelle="Description *" valeur={v.description} onChange={(x) => f.maj("description", x)} placeholder="Vidange + filtres" /><Texte libelle="Prestataire (garage, mécanicien)" valeur={v.prestataire} onChange={(x) => f.maj("prestataire", x)} />
      <div className="grid grid-cols-3 gap-x-3"><div className="col-span-2"><Liste libelle="Pièce utilisée (facultatif)" valeur={v.piece_id} onChange={(x) => f.maj("piece_id", x)} vide="Aucune" options={pieces.map((p) => ({ valeur: p.id, libelle: `${p.designation} (stock ${p.stock})` }))} /></div><Texte libelle="Quantité" type="number" valeur={v.quantite} onChange={(x) => f.maj("quantite", x)} min="1" /></div>
    </Modal>
  );
}

export default function Parc() {
  const { parametres, utilisateur, avecToast, rafraichirCompteurs } = useApp();
  const [onglet, setOnglet] = useState("vehicules");
  const [veh, setVeh] = useState(null);
  const [alertes, setAlertes] = useState([]);
  const [pannes, setPannes] = useState([]);
  const [ints, setInts] = useState([]);
  const [synth, setSynth] = useState(null);
  const [ouvert, setOuvert] = useState("");
  const [nouveau, setNouveau] = useState("");
  const t1 = useTri(); const t2 = useTri(); const t3 = useTri(); const t4 = useTri();
  const peutGerer = ["mecanicien", "gestionnaire", "directeur", "super_admin"].includes(utilisateur.role);
  const voirCouts = ["comptable", "mecanicien", "gestionnaire", "directeur", "super_admin"].includes(utilisateur.role);
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => Promise.all([api("/parc/vehicules").then(setVeh), api("/parc/alertes").then(setAlertes), api("/parc/pannes").then(setPannes), api("/parc/interventions").then(setInts),
    voirCouts ? api("/parc/synthese").then(setSynth) : null]).then(rafraichirCompteurs), [voirCouts, rafraichirCompteurs]);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const action = (nom, chemin, corps, ok) => avecToast(nom, () => api(chemin, { methode: "POST", corps }), () => ok).then(charger).catch(() => {});
  const resoudre = (p) => avecToast("Résolution de la panne", () => api(`/parc/pannes/${p.id}`, { methode: "PUT", corps: { statut: "resolue" } }), () => "Panne résolue").then(charger).catch(() => {});
  if (!veh) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const ONGLETS = [["vehicules", `Véhicules (${veh.length})`], ["alertes", `Alertes (${alertes.length})`], ["pannes", `Pannes (${pannes.filter((p) => p.statut !== "resolue").length})`], ["interventions", "Interventions"], ...(voirCouts ? [["couts", "Coûts"]] : [])];
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Parc automobile</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation du parc", charger, () => `${veh.length} véhicule(s), ${alertes.length} alerte(s)`)}>Actualiser</Bouton>
          {peutGerer && <Bouton icone={Wrench} petit onClick={() => setNouveau("intervention")}>Planifier une intervention</Bouton>}{peutGerer && <Bouton icone={Plus} variante="principal" petit onClick={() => setNouveau("vehicule")}>Nouveau véhicule</Bouton>}</div></div>
      <div className="mt-3 flex flex-wrap gap-1 border-b border-slate-200">{ONGLETS.map(([k, l]) => <button key={k} onClick={() => setOnglet(k)} className={`rounded-t-xl px-4 py-2 text-sm font-semibold ${onglet === k ? "bg-white text-emeraude ring-1 ring-slate-200" : "text-ardoise hover:text-encre"}`}>{l}</button>)}</div>
      <div className="rounded-b-2xl rounded-tr-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        {onglet === "vehicules" && <table className="tableau"><thead><tr><ThTri cle="immatriculation" tri={t1}>Immatriculation</ThTri><ThTri cle="marque" tri={t1}>Véhicule</ThTri><ThTri cle="type_libelle" tri={t1}>Type</ThTri><ThTri cle="km_actuel" tri={t1} numerique>Kilométrage</ThTri><ThTri cle="statut" tri={t1}>Statut</ThTri><th>Échéances</th><ThTri cle="pannes_ouvertes" tri={t1} numerique>Pannes</ThTri></tr></thead>
          <tbody>{trierLignes(veh, t1.cle, t1.sens).map((v) => <tr key={v.id} className={ouvert === v.id ? "ligne-selectionnee" : ""} onClick={() => setOuvert(v.id)} style={{ cursor: "pointer" }}><td className="font-semibold text-emeraude">{v.immatriculation}</td><td>{v.marque} {v.modele}</td><td>{v.type_libelle}</td><td className="num">{v.km_actuel.toLocaleString("fr-FR")} km</td>
            <td><Pastille couleur={STATUT[v.statut][1]}>{STATUT[v.statut][0]}</Pastille></td><td>{v.echeances_proches.length ? <Pastille couleur="orange" icone={AlertTriangle}>{v.echeances_proches.join(", ")}</Pastille> : <span className="text-slate-400">—</span>}</td><td className="num">{v.pannes_ouvertes || ""}</td></tr>)}
            {!veh.length && <tr><td colSpan={7} className="text-slate-500">Aucun véhicule : ajoutez le premier.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{veh.length} véhicule(s)</td><td colSpan={2} /><td className="num">{veh.reduce((a, v) => a + v.km_actuel, 0).toLocaleString("fr-FR")} km</td><td colSpan={2} /><td className="num">{veh.reduce((a, v) => a + v.pannes_ouvertes, 0)}</td></tr></tfoot></table>}
        {onglet === "alertes" && <ul className="divide-y divide-slate-100">{alertes.map((a, i) => <li key={i} className="flex items-center gap-3 px-4 py-2.5 text-sm"><Pastille couleur={a.niveau === "rouge" ? "rouge" : "orange"} icone={AlertTriangle}>{a.niveau === "rouge" ? "Urgent" : "À prévoir"}</Pastille><b className="text-emeraude">{a.immatriculation}</b><span>{a.message}</span></li>)}
          {!alertes.length && <li className="flex items-center gap-2 px-4 py-4 text-sm text-emerald-700"><CheckCircle2 size={18} />Aucune alerte : le parc est à jour.</li>}</ul>}
        {onglet === "pannes" && <table className="tableau"><thead><tr><ThTri cle="date" tri={t2}>Date</ThTri><ThTri cle="immatriculation" tri={t2}>Véhicule</ThTri><ThTri cle="description" tri={t2}>Description</ThTri><ThTri cle="gravite" tri={t2}>Gravité</ThTri><ThTri cle="signale_par" tri={t2}>Signalée par</ThTri><ThTri cle="statut" tri={t2}>État</ThTri><th /></tr></thead>
          <tbody>{trierLignes(pannes, t2.cle, t2.sens).map((p) => <tr key={p.id}><td>{dateFr(p.date)}</td><td className="font-semibold text-emeraude">{p.immatriculation}</td><td>{p.description}</td><td><Pastille couleur={{ mineure: "gris", majeure: "orange", immobilisante: "rouge" }[p.gravite]}>{{ mineure: "Mineure", majeure: "Majeure", immobilisante: "Immobilisante" }[p.gravite]}</Pastille></td><td>{p.signale_par}</td>
            <td><Pastille couleur={p.statut === "resolue" ? "vert" : "orange"}>{{ ouverte: "Ouverte", en_cours: "En cours", resolue: "Résolue" }[p.statut]}</Pastille></td><td>{peutGerer && p.statut !== "resolue" && <Bouton petit variante="vert" icone={CheckCircle2} onClick={() => resoudre(p)}>Résoudre</Bouton>}</td></tr>)}
            {!pannes.length && <tr><td colSpan={7} className="text-slate-500">Aucune panne.</td></tr>}</tbody><tfoot><tr className="font-bold bg-brume"><td>{pannes.length} panne(s)</td><td colSpan={6} /></tr></tfoot></table>}
        {onglet === "interventions" && <table className="tableau"><thead><tr><ThTri cle="date" tri={t3}>Date</ThTri><ThTri cle="immatriculation" tri={t3}>Véhicule</ThTri><ThTri cle="type" tri={t3}>Type</ThTri><ThTri cle="description" tri={t3}>Description</ThTri><ThTri cle="statut" tri={t3}>État</ThTri>{voirCouts && <ThTri cle="cout_total" tri={t3} numerique>Coût</ThTri>}<th /></tr></thead>
          <tbody>{trierLignes(ints, t3.cle, t3.sens).map((i) => <tr key={i.id}><td>{dateFr(i.date)}</td><td className="font-semibold text-emeraude">{i.immatriculation}</td><td>{{ entretien: "Entretien", reparation: "Réparation", controle: "Contrôle", autre: "Autre" }[i.type]}</td><td>{i.description}{i.pieces?.length > 0 && <div className="text-xs text-slate-500">{i.pieces.map((p) => `${p.quantite} × ${p.designation}`).join(", ")}</div>}</td>
            <td><Pastille couleur={{ planifiee: "bleu", en_cours: "orange", terminee: "vert", annulee: "gris" }[i.statut]}>{{ planifiee: "Planifiée", en_cours: "En cours", terminee: "Terminée", annulee: "Annulée" }[i.statut]}</Pastille></td>{voirCouts && <td className="num">{i.cout_total != null ? m(i.cout_total) : ""}</td>}
            <td className="whitespace-nowrap">{peutGerer && i.statut === "planifiee" && <Bouton petit icone={Play} onClick={() => action("Démarrage", `/parc/interventions/${i.id}/demarrer`, undefined, "Intervention démarrée")}>Démarrer</Bouton>}
              {peutGerer && ["planifiee", "en_cours"].includes(i.statut) && <Bouton petit variante="vert" icone={CheckCircle2} className="ml-1" onClick={() => { const mo = window.prompt("Coût de main-d'œuvre (0 si aucun) :", "0"); if (mo !== null) action("Clôture", `/parc/interventions/${i.id}/terminer`, { cout_main_oeuvre: mo }, "Intervention terminée"); }}>Terminer</Bouton>}</td></tr>)}
            {!ints.length && <tr><td colSpan={7} className="text-slate-500">Aucune intervention.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{ints.length} intervention(s)</td><td colSpan={4} />{voirCouts && <td className="num">{m(ints.reduce((a, i) => a + (i.cout_total || 0), 0))}</td>}<td /></tr></tfoot></table>}
        {onglet === "couts" && synth && <table className="tableau"><thead><tr><ThTri cle="immatriculation" tri={t4}>Véhicule</ThTri><ThTri cle="km_periode" tri={t4} numerique>Km parcourus</ThTri><ThTri cle="litres" tri={t4} numerique>Litres</ThTri><ThTri cle="carburant" tri={t4} numerique>Carburant</ThTri><ThTri cle="maintenance" tri={t4} numerique>Maintenance</ThTri><ThTri cle="total" tri={t4} numerique>Total</ThTri><ThTri cle="cout_au_km" tri={t4} numerique>Coût au km</ThTri></tr></thead>
          <tbody>{trierLignes(synth.vehicules, t4.cle, t4.sens).map((l) => <tr key={l.id}><td className="font-semibold text-emeraude">{l.immatriculation}<div className="text-xs font-normal text-slate-500">{l.marque} {l.modele}</div></td><td className="num">{l.km_periode.toLocaleString("fr-FR")}</td><td className="num">{l.litres}</td><td className="num">{m(l.carburant)}</td><td className="num">{m(l.maintenance)}</td><td className="num font-bold">{m(l.total)}</td><td className="num">{l.cout_au_km ? m(l.cout_au_km) : "—"}</td></tr>)}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{synth.vehicules.length} véhicule(s)</td><td className="num">{synth.vehicules.reduce((a, l) => a + l.km_periode, 0).toLocaleString("fr-FR")}</td><td className="num">{Math.round(synth.vehicules.reduce((a, l) => a + l.litres, 0) * 10) / 10}</td><td className="num">{m(synth.total_carburant)}</td><td className="num">{m(synth.total_maintenance)}</td><td className="num">{m(synth.total_carburant + synth.total_maintenance)}</td><td /></tr></tfoot></table>}
      </div>
      {ouvert && <Vehicule id={ouvert} onFermer={() => setOuvert("")} onChange={charger} />}
      {nouveau === "vehicule" && <NouveauVehicule onFermer={() => setNouveau("")} onFait={() => { setNouveau(""); charger(); }} />}
      {nouveau === "intervention" && <Intervention vehicules={veh.filter((v) => v.statut !== "reforme")} onFermer={() => setNouveau("")} onFait={() => { setNouveau(""); setOnglet("interventions"); charger(); }} />}
    </div>
  );
}
