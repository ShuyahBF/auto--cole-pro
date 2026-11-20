// Tarifs (forfaits par catégorie) et promotions. Création / modification en fenêtre modale ; un tarif utilisé se désactive, il ne se supprime pas.
import { Pencil, Plus, Power, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Bouton, { BoutonIcone } from "../composants/Bouton.jsx";
import { Liste, Pastille, Texte } from "../composants/Champs.jsx";
import Modal from "../composants/Modal.jsx";
import ThTri from "../composants/ThTri.jsx";
import { api } from "../lib/api.js";
import { useApp, useFormulaire } from "../lib/contexte.jsx";
import { dateFr, montant } from "../lib/format.js";
import { trierLignes, useTri } from "../lib/tri.js";

function TarifModal({ tarif, onFermer, onFait }) {
  const { parametres, avecToast } = useApp();
  const f = useFormulaire(tarif || { code: "", libelle: "", categorie: "", prix: "", heures_conduite: 20, seances_code: 10, acompte_minimum: 0, description: "" });
  const v = f.valeurs;
  const enregistrer = () => avecToast("Enregistrement du tarif", () => (tarif ? api(`/tarifs/${tarif.id}`, { methode: "PUT", corps: v }) : api("/tarifs", { methode: "POST", corps: v })), () => "Tarif enregistré").then(onFait).catch(() => {});
  return (
    <Modal titre={tarif ? "Modifier le tarif" : "Nouveau tarif"} onFermer={onFermer} pied={<>
      <Bouton icone={Save} variante="principal" disabled={!f.modifie} onClick={enregistrer}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton>
      {f.modifie && <span className="self-center text-xs text-orange-700">modifié, non enregistré</span>}</>}>
      {!tarif && <Texte libelle="Code *" valeur={v.code} onChange={(x) => f.maj("code", x)} placeholder="B-STANDARD" />}
      <Texte libelle="Libellé *" valeur={v.libelle} onChange={(x) => f.maj("libelle", x)} placeholder="Permis B — formule standard" />
      <Liste libelle="Catégorie de permis *" valeur={v.categorie} onChange={(x) => f.maj("categorie", x)} options={(parametres?.categories || []).map((c) => ({ valeur: c.code, libelle: `${c.code} — ${c.libelle}` }))} />
      <div className="grid gap-x-3 grid-cols-2">
        <Texte libelle={`Prix * (${parametres?.devise || ""})`} type="number" valeur={v.prix} onChange={(x) => f.maj("prix", x)} min="0" />
        <Texte libelle="Acompte minimum" type="number" valeur={v.acompte_minimum} onChange={(x) => f.maj("acompte_minimum", x)} min="0" />
        <Texte libelle="Heures de conduite" type="number" valeur={v.heures_conduite} onChange={(x) => f.maj("heures_conduite", x)} min="0" />
        <Texte libelle="Séances de code" type="number" valeur={v.seances_code} onChange={(x) => f.maj("seances_code", x)} min="0" />
      </div>
      <Texte libelle="Description" valeur={v.description} onChange={(x) => f.maj("description", x)} />
    </Modal>
  );
}

function PromoModal({ onFermer, onFait }) {
  const { parametres, avecToast } = useApp();
  const f = useFormulaire({ code: "", libelle: "", type: "pourcentage", valeur: "", debut: "", fin: "" });
  const v = f.valeurs;
  const enregistrer = () => avecToast("Enregistrement de la promotion", () => api("/promotions", { methode: "POST", corps: v }), () => "Promotion enregistrée").then(onFait).catch(() => {});
  return (
    <Modal titre="Nouvelle promotion" onFermer={onFermer} pied={<><Bouton icone={Save} variante="principal" disabled={!f.modifie} onClick={enregistrer}>Enregistrer</Bouton><Bouton onClick={onFermer}>Annuler</Bouton></>}>
      <Texte libelle="Code *" valeur={v.code} onChange={(x) => f.maj("code", x)} placeholder="RENTREE" /><Texte libelle="Libellé *" valeur={v.libelle} onChange={(x) => f.maj("libelle", x)} />
      <div className="grid grid-cols-2 gap-x-3">
        <Liste libelle="Type de remise" valeur={v.type} onChange={(x) => f.maj("type", x)} vide={null} options={[{ valeur: "pourcentage", libelle: "Pourcentage" }, { valeur: "montant", libelle: `Montant (${parametres?.devise || ""})` }]} />
        <Texte libelle="Valeur *" type="number" valeur={v.valeur} onChange={(x) => f.maj("valeur", x)} min="0" />
        <Texte libelle="Début" type="date" valeur={v.debut} onChange={(x) => f.maj("debut", x)} /><Texte libelle="Fin" type="date" valeur={v.fin} onChange={(x) => f.maj("fin", x)} />
      </div>
    </Modal>
  );
}

export default function Tarifs() {
  const { parametres, utilisateur, avecToast } = useApp();
  const [tarifs, setTarifs] = useState(null);
  const [promos, setPromos] = useState([]);
  const [edition, setEdition] = useState(null);       // null | "nouveau" | tarif
  const [promoModal, setPromoModal] = useState(false);
  const t1 = useTri();
  const t2 = useTri();
  const peutEcrire = ["super_admin", "directeur", "gestionnaire"].includes(utilisateur.role);
  const m = (x) => montant(x, parametres?.devise, parametres?.decimales);
  const charger = useCallback(() => Promise.all([api("/tarifs").then(setTarifs), api("/promotions").then(setPromos)]), []);
  useEffect(() => { charger().catch(() => {}); }, [charger]);
  const basculer = (url, actif) => avecToast("Mise à jour", () => api(url, { methode: "PUT", corps: { actif: !actif } }), () => (actif ? "Désactivé" : "Activé")).then(charger).catch(() => {});
  if (!tarifs) return <div className="py-10 flex justify-center"><span className="jauge" /></div>;
  const ETAT = { en_cours: ["En cours", "vert"], a_venir: ["À venir", "bleu"], terminee: ["Terminée", "gris"], inactive: ["Inactive", "gris"] };
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Tarifs et promotions</h1>
        <div className="flex gap-2"><Bouton icone={RefreshCw} petit onClick={() => avecToast("Actualisation des tarifs", charger, () => "Tarifs actualisés")}>Actualiser</Bouton>
          {peutEcrire && <Bouton icone={Plus} variante="principal" petit onClick={() => setEdition("nouveau")}>Nouveau tarif</Bouton>}</div>
      </div>
      <div className="mt-3 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="code" tri={t1}>Code</ThTri><ThTri cle="libelle" tri={t1}>Forfait</ThTri><ThTri cle="categorie" tri={t1}>Permis</ThTri><ThTri cle="prix" tri={t1} numerique>Prix</ThTri><ThTri cle="heures_conduite" tri={t1} numerique>Heures conduite</ThTri><ThTri cle="seances_code" tri={t1} numerique>Séances code</ThTri><th>État</th><th /></tr></thead>
          <tbody>{trierLignes(tarifs, t1.cle, t1.sens).map((t) => (
            <tr key={t.id} className={t.actif ? "" : "opacity-60"}><td className="font-semibold text-emeraude">{t.code}</td><td>{t.libelle}</td><td>{t.categorie}</td><td className="num font-semibold">{m(t.prix)}</td><td className="num">{t.heures_conduite}</td><td className="num">{t.seances_code}</td>
              <td>{t.actif ? <Pastille couleur="vert">Actif</Pastille> : <Pastille>Désactivé</Pastille>}</td>
              <td className="whitespace-nowrap">{peutEcrire && <><BoutonIcone icone={Pencil} libelle="Modifier" onClick={() => setEdition(t)} /><BoutonIcone icone={Power} libelle={t.actif ? "Désactiver" : "Réactiver"} couleur={t.actif ? "text-rose-600" : "text-emerald-600"} onClick={() => basculer(`/tarifs/${t.id}`, t.actif)} /></>}</td></tr>))}
            {!tarifs.length && <tr><td colSpan={8} className="text-slate-500">Aucun tarif : créez votre premier forfait.</td></tr>}</tbody></table>
      </div>
      <div className="mt-6 flex items-center justify-between"><h2 className="text-lg font-semibold">Promotions</h2>{peutEcrire && <Bouton icone={Plus} petit onClick={() => setPromoModal(true)}>Nouvelle promotion</Bouton>}</div>
      <div className="mt-2 rounded-2xl bg-white ring-1 ring-encre/5 overflow-x-auto">
        <table className="tableau"><thead><tr><ThTri cle="code" tri={t2}>Code</ThTri><ThTri cle="libelle" tri={t2}>Libellé</ThTri><ThTri cle="valeur" tri={t2} numerique>Remise</ThTri><ThTri cle="debut" tri={t2}>Début</ThTri><ThTri cle="fin" tri={t2}>Fin</ThTri><th>État</th><th /></tr></thead>
          <tbody>{trierLignes(promos, t2.cle, t2.sens).map((p) => (
            <tr key={p.id}><td className="font-semibold text-emeraude">{p.code}</td><td>{p.libelle}</td><td className="num">{p.type === "pourcentage" ? `${p.valeur} %` : m(p.valeur)}</td><td>{dateFr(p.debut)}</td><td>{dateFr(p.fin)}</td>
              <td><Pastille couleur={ETAT[p.etat][1]}>{ETAT[p.etat][0]}</Pastille></td><td>{peutEcrire && <BoutonIcone icone={Power} libelle={p.actif ? "Désactiver" : "Réactiver"} couleur={p.actif ? "text-rose-600" : "text-emerald-600"} onClick={() => basculer(`/promotions/${p.id}`, p.actif)} />}</td></tr>))}
            {!promos.length && <tr><td colSpan={7} className="text-slate-500">Aucune promotion.</td></tr>}</tbody></table>
      </div>
      {edition && <TarifModal tarif={edition === "nouveau" ? null : edition} onFermer={() => setEdition(null)} onFait={() => { setEdition(null); charger(); }} />}
      {promoModal && <PromoModal onFermer={() => setPromoModal(false)} onFait={() => { setPromoModal(false); charger(); }} />}
    </div>
  );
}
