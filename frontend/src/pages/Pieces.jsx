// Pièces détachées et approvisionnement : catalogue et stock, suggestions de réapprovisionnement, fournisseurs, bons de commande (réception = entrée en stock).
// Détails et saisies en fenêtres modales (règle 20) ; totaux sous les tableaux (règle 25).
import { PackagePlus, Plus, RefreshCw, Save, Truck, CheckCircle2, ShoppingCart } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton from "../composants/Bouton.jsx";
import { Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { dateFr, montant } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

const CATEGORIES = [["moteur", "Moteur"], ["freinage", "Freinage"], ["pneumatique", "Pneumatiques"], ["electricite", "Électricité"], ["transmission", "Transmission"], ["carrosserie", "Carrosserie"], ["filtration", "Filtres et fluides"], ["autre", "Autre"]].map(([valeur, libelle]) => ({ valeur, libelle }));

function NouvellePiece({ onFermer, onFait, prix }) {
  const { avecToast } = useApp();
  const f = useFormulaire({ reference: "", designation: "", categorie: "autre", unite: "pièce", stock: 0, seuil_alerte: 0, prix_unitaire: "", emplacement: "" });
  const v = f.valeurs;
  return (
    <Modal titre="Nouvelle pièce" onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!v.reference || !v.designation} onClick={() => avecToast("Création de la pièce", () => api("/parc/pieces", { methode: "POST", corps: v }), () => "Pièce créée").then(onFait).catch(() => {})}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <div className="grid grid-cols-2 gap-x-3"><Texte libelle="Référence *" valeur={v.reference} onChange={(x) => f.maj("reference", x)} /><Texte libelle="Désignation *" valeur={v.designation} onChange={(x) => f.maj("designation", x)} />
        <Liste libelle="Catégorie" valeur={v.categorie} onChange={(x) => f.maj("categorie", x)} vide={null} options={CATEGORIES} /><Texte libelle="Unité" valeur={v.unite} onChange={(x) => f.maj("unite", x)} />
        <Texte libelle="Stock initial" type="number" valeur={v.stock} onChange={(x) => f.maj("stock", x)} min="0" /><Texte libelle="Seuil d'alerte" type="number" valeur={v.seuil_alerte} onChange={(x) => f.maj("seuil_alerte", x)} min="0" />
        {prix && <Texte libelle="Prix unitaire" type="number" valeur={v.prix_unitaire} onChange={(x) => f.maj("prix_unitaire", x)} min="0" />}<Texte libelle="Emplacement" valeur={v.emplacement} onChange={(x) => f.maj("emplacement", x)} /></div>
    </Modal>
  );
}

function Mouvement({ piece, onFermer, onFait }) {
  const { avecToast } = useApp();
  const [n, setN] = useState({ type: "entree", quantite: "", motif: "" });
  return (
    <Modal titre={`Mouvement de stock — ${piece.designation}`} onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={n.quantite === ""} onClick={() => avecToast("Enregistrement du mouvement", () => api(`/parc/pieces/${piece.id}/mouvement`, { methode: "POST", corps: n }), () => "Mouvement enregistré").then(onFait).catch(() => {})}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <p className="mb-2 text-sm">Stock actuel : <b>{piece.stock} {piece.unite}</b></p>
      <Liste libelle="Type" valeur={n.type} onChange={(x) => setN({ ...n, type: x })} vide={null} options={[{ valeur: "entree", libelle: "Entrée" }, { valeur: "sortie", libelle: "Sortie" }, { valeur: "ajustement", libelle: "Ajustement d'inventaire (nouveau stock)" }]} />
      <Texte libelle="Quantité" type="number" valeur={n.quantite} onChange={(x) => setN({ ...n, quantite: x })} min="0" /><Texte libelle={n.type === "ajustement" ? "Motif *" : "Motif"} valeur={n.motif} onChange={(x) => setN({ ...n, motif: x })} />
    </Modal>
  );
}

function NouvelleCommande({ pieces, fournisseurs, depart, onFermer, onFait }) {
  const { avecToast } = useApp();
  const [fid, setFid] = useState("");
  const [lignes, setLignes] = useState(depart);
  const maj = (i, c, v) => setLignes(lignes.map((l, j) => (j === i ? { ...l, [c]: v } : l)));
  const go = (envoyer) => avecToast("Création de la commande", () => api("/parc/commandes", { methode: "POST", corps: { fournisseur_id: fid, envoyer, lignes } }), (c) => `Commande ${c.numero} créée`).then(onFait).catch(() => {});
  return (
    <Modal titre="Bon de commande" large onFermer={onFermer} pied={<><Bouton icone={Save} petit disabled={!fid || !lignes.length} onClick={() => go(false)}>Brouillon</Bouton><Bouton icone={Truck} variante="principal" disabled={!fid || !lignes.length} onClick={() => go(true)}>Commander</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Liste libelle="Fournisseur *" valeur={fid} onChange={setFid} options={fournisseurs.filter((f) => f.actif).map((f) => ({ valeur: f.id, libelle: f.nom }))} />
      {lignes.map((l, i) => <div key={i} className="grid grid-cols-6 items-end gap-x-2"><div className="col-span-3"><Liste libelle="Pièce" valeur={l.piece_id} onChange={(x) => maj(i, "piece_id", x)} options={pieces.map((p) => ({ valeur: p.id, libelle: p.designation }))} /></div>
        <Texte libelle="Quantité" type="number" valeur={l.quantite} onChange={(x) => maj(i, "quantite", x)} min="1" /><div className="col-span-2"><Texte libelle="Prix unitaire" type="number" valeur={l.prix_unitaire} onChange={(x) => maj(i, "prix_unitaire", x)} min="0" /></div></div>)}
      <Bouton icone={Plus} petit onClick={() => setLignes([...lignes, { piece_id: "", quantite: 1, prix_unitaire: "" }])}>Ajouter une ligne</Bouton>
    </Modal>
  );
}

export default function Pieces() {
  const { parametres, avecToast } = useApp();
  const [onglet, setOnglet] = useState("pieces");
  const [pieces, setPieces] = useState(null);
  const [sug, setSug] = useState([]);
  const [fourn, setFourn] = useState([]);
  const [cmd, setCmd] = useState([]);
  const [modal, setModal] = useState(null);       // {type, ...}
  const [nf, setNf] = useState("");
  const t1 = useTri(); const t2 = useTri(); const t3 = useTri();
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => Promise.all([api("/parc/pieces").then(setPieces), api("/parc/suggestions").then(setSug), api("/parc/fournisseurs").then(setFourn), api("/parc/commandes").then(setCmd)]), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  if (!pieces) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const prix = pieces.some((p) => "prix_unitaire" in p) || true;
  const recevoir = (c) => avecToast("Réception de la commande", () => api(`/parc/commandes/${c.id}/statut`, { methode: "POST", corps: { statut: "recue" } }), () => `${c.numero} reçue : stock mis à jour`).then(charger).catch(() => {});
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-bold">Pièces et approvisionnement</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation du stock", charger, () => `${pieces.length} pièce(s), ${sug.length} à réapprovisionner`)}>Actualiser</Bouton>
          <Bouton icone={ShoppingCart} petit onClick={() => setModal({ type: "commande", depart: sug.length ? sug.map((s) => ({ piece_id: s.piece_id, quantite: s.quantite_conseillee, prix_unitaire: s.prix_unitaire ?? "" })) : [{ piece_id: "", quantite: 1, prix_unitaire: "" }] })}>{sug.length ? `Commander les ${sug.length} pièce(s) sous le seuil` : "Nouvelle commande"}</Bouton>
          <Bouton icone={PackagePlus} variante="principal" petit onClick={() => setModal({ type: "piece" })}>Nouvelle pièce</Bouton></div></div>
      <div className="mt-3 flex flex-wrap gap-1 border-b border-slate-200">{[["pieces", `Pièces (${pieces.length})`], ["commandes", `Commandes (${cmd.length})`], ["fournisseurs", `Fournisseurs (${fourn.length})`]].map(([k, l]) => <button key={k} onClick={() => setOnglet(k)} className={`rounded-t-xl px-4 py-2 text-sm font-semibold ${onglet === k ? "bg-white text-emeraude ring-1 ring-slate-200" : "text-ardoise"}`}>{l}</button>)}</div>
      <div className="rounded-b-2xl rounded-tr-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        {onglet === "pieces" && <table className="tableau"><thead><tr><ThTri cle="reference" tri={t1}>Référence</ThTri><ThTri cle="designation" tri={t1}>Désignation</ThTri><ThTri cle="categorie_libelle" tri={t1}>Catégorie</ThTri><ThTri cle="stock" tri={t1} numerique>Stock</ThTri><ThTri cle="seuil_alerte" tri={t1} numerique>Seuil</ThTri><ThTri cle="prix_unitaire" tri={t1} numerique>Prix unitaire</ThTri><th>État</th><th /></tr></thead>
          <tbody>{trierLignes(pieces, t1.cle, t1.sens).map((p) => <tr key={p.id}><td className="font-semibold text-emeraude">{p.reference}</td><td>{p.designation}</td><td>{p.categorie_libelle}</td><td className="num font-bold">{p.stock}</td><td className="num">{p.seuil_alerte}</td><td className="num">{p.prix_unitaire != null ? m(p.prix_unitaire) : ""}</td>
            <td>{p.a_commander ? <Pastille couleur={p.stock <= 0 ? "rouge" : "orange"}>{p.stock <= 0 ? "Rupture" : "À commander"}</Pastille> : <Pastille couleur="vert">Suffisant</Pastille>}</td><td><Bouton petit onClick={() => setModal({ type: "mouvement", piece: p })}>Mouvement</Bouton></td></tr>)}
            {!pieces.length && <tr><td colSpan={8} className="text-slate-500">Aucune pièce : ajoutez la première.</td></tr>}</tbody>
          <tfoot><tr className="font-bold bg-brume"><td>{pieces.length} pièce(s)</td><td colSpan={2} /><td className="num">{pieces.reduce((a, p) => a + p.stock, 0)}</td><td /><td className="num">{m(pieces.reduce((a, p) => a + p.stock * (p.prix_unitaire || 0), 0))}</td><td colSpan={2}>valeur du stock</td></tr></tfoot></table>}
        {onglet === "commandes" && <table className="tableau"><thead><tr><ThTri cle="numero" tri={t2}>N°</ThTri><ThTri cle="date_commande" tri={t2}>Date</ThTri><ThTri cle="fournisseur_nom" tri={t2}>Fournisseur</ThTri><th>Lignes</th><ThTri cle="total" tri={t2} numerique>Total</ThTri><ThTri cle="statut" tri={t2}>État</ThTri><th /></tr></thead>
          <tbody>{trierLignes(cmd, t2.cle, t2.sens).map((c) => <tr key={c.id}><td className="font-semibold text-emeraude">{c.numero}</td><td>{dateFr(c.date_commande)}</td><td>{c.fournisseur_nom}</td><td className="text-xs">{c.lignes.map((l) => `${l.quantite} × ${l.designation}`).join(", ")}</td><td className="num">{m(c.total)}</td><td><Pastille couleur={{ brouillon: "gris", commandee: "bleu", recue: "vert", annulee: "gris" }[c.statut]}>{c.statut_libelle}</Pastille></td>
            <td className="whitespace-nowrap">{c.statut === "brouillon" && <Bouton petit icone={Truck} onClick={() => avecToast("Envoi", () => api(`/parc/commandes/${c.id}/statut`, { methode: "POST", corps: { statut: "commandee" } }), () => "Commandée").then(charger)}>Commander</Bouton>}{c.statut === "commandee" && <Bouton petit variante="vert" icone={CheckCircle2} onClick={() => recevoir(c)}>Réceptionner</Bouton>}</td></tr>)}
            {!cmd.length && <tr><td colSpan={7} className="text-slate-500">Aucune commande.</td></tr>}</tbody><tfoot><tr className="font-bold bg-brume"><td>{cmd.length} commande(s)</td><td colSpan={3} /><td className="num">{m(cmd.filter((c) => c.statut !== "annulee").reduce((a, c) => a + c.total, 0))}</td><td colSpan={2} /></tr></tfoot></table>}
        {onglet === "fournisseurs" && <><table className="tableau"><thead><tr><ThTri cle="nom" tri={t3}>Fournisseur</ThTri><ThTri cle="telephone" tri={t3}>Téléphone</ThTri><ThTri cle="produits" tri={t3}>Produits</ThTri><th>État</th></tr></thead>
          <tbody>{trierLignes(fourn, t3.cle, t3.sens).map((f) => <tr key={f.id}><td className="font-semibold">{f.nom}</td><td>{f.telephone}</td><td>{f.produits}</td><td>{f.actif ? <Pastille couleur="vert">Actif</Pastille> : <Pastille>Désactivé</Pastille>}</td></tr>)}</tbody><tfoot><tr className="font-bold bg-brume"><td>{fourn.length} fournisseur(s)</td><td colSpan={3} /></tr></tfoot></table>
          <div className="flex items-end gap-2 p-3"><div className="flex-1"><Texte libelle="Nouveau fournisseur" valeur={nf} onChange={setNf} placeholder="Auto Pièces SA" /></div><div className="pb-3"><Bouton icone={Plus} petit disabled={!nf.trim()} onClick={() => avecToast("Création du fournisseur", () => api("/parc/fournisseurs", { methode: "POST", corps: { nom: nf } }), () => "Fournisseur créé").then(() => { setNf(""); charger(); }).catch(() => {})}>Ajouter</Bouton></div></div></>}
      </div>
      {modal?.type === "piece" && <NouvellePiece prix={prix} onFermer={() => setModal(null)} onFait={() => { setModal(null); charger(); }} />}
      {modal?.type === "mouvement" && <Mouvement piece={modal.piece} onFermer={() => setModal(null)} onFait={() => { setModal(null); charger(); }} />}
      {modal?.type === "commande" && <NouvelleCommande pieces={pieces} fournisseurs={fourn} depart={modal.depart} onFermer={() => setModal(null)} onFait={() => { setModal(null); setOnglet("commandes"); charger(); }} />}
    </div>
  );
}
