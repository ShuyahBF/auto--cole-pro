// Champs de formulaire communs : étiquette + saisie, liste déroulante (listes finies : règle 10), case à cocher.
export const classeChamp = "w-full rounded-lg border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white";

/** Un intitulé qui se termine par « * » désigne un champ OBLIGATOIRE : l'étoile est collée au mot (« Nom* »), en rouge, et l'étiquette est marquée pour le contrôle
 *  à la validation de la fiche (lib/validationFormulaires.js : champs vides en fond rouge). */
export function decouperIntitule(libelle) {
  const brut = String(libelle ?? "");
  const requis = /\s*\*\s*$/.test(brut);
  return { texte: requis ? brut.replace(/\s*\*\s*$/, "") : brut, requis };
}

export function Champ({ libelle, children, aide }) {
  const { texte, requis } = decouperIntitule(libelle);
  return (
    <label className="block mb-3" {...(requis ? { "data-requis": "oui" } : {})}>
      <span className="mb-1 block text-xs font-semibold tracking-wide text-ardoise"><span data-intitule>{texte}</span>{requis && <span className="text-rose-600" aria-hidden="true">*</span>}{requis && <span className="sr-only"> (obligatoire)</span>}</span>
      {children}
      {aide && <span className="block text-xs text-slate-500 mt-1">{aide}</span>}
    </label>
  );
}

/** Règle du propriétaire (21/11/2026) : un champ CLÉ d'une fiche (nom de l'auto-école, code, référence, immatriculation…) est en MAJUSCULES (`majuscules`) ;
 *  un nom ordinaire (ex. une agence « Bobo ») prend seulement une 1re lettre majuscule (`premiereMajuscule`). */
export function transformer(valeur, majuscules, premiereMajuscule) {
  if (majuscules) return valeur.toLocaleUpperCase("fr-FR");
  if (premiereMajuscule) return valeur.charAt(0).toLocaleUpperCase("fr-FR") + valeur.slice(1);
  return valeur;
}


export function Texte({ libelle, valeur, onChange, type = "text", placeholder, aide, majuscules = false, premiereMajuscule = false, ...autres }) {
  return (
    <Champ libelle={libelle} aide={aide}>
      <input type={type} value={valeur ?? ""} onChange={(e) => onChange(transformer(e.target.value, majuscules, premiereMajuscule))} placeholder={placeholder}
        className={`${classeChamp}${majuscules ? " uppercase" : ""}`} {...autres} />
    </Champ>
  );
}

/** Liste déroulante. `options` : tableau de chaînes ou de {valeur, libelle}. Une valeur déjà enregistrée absente de la liste reste sélectionnable. */
export function Liste({ libelle, valeur, onChange, options, vide = "— Choisir —", aide }) {
  const opts = options.map((o) => (typeof o === "string" ? { valeur: o, libelle: o } : o));
  const inconnue = valeur && !opts.some((o) => o.valeur === valeur);
  return (
    <Champ libelle={libelle} aide={aide}>
      <select value={valeur ?? ""} onChange={(e) => onChange(e.target.value)} className={classeChamp}>
        {vide !== null && <option value="">{vide}</option>}
        {inconnue && <option value={valeur}>{valeur}</option>}
        {opts.map((o) => <option key={o.valeur} value={o.valeur}>{o.libelle}</option>)}
      </select>
    </Champ>
  );
}

export function Case({ libelle, valeur, onChange }) {
  return (
    <label className="flex items-center gap-2 mb-3 cursor-pointer">
      <input type="checkbox" checked={!!valeur} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-emeraude" />
      <span className="text-sm">{libelle}</span>
    </label>
  );
}

/** Pastille d'état : couleur + texte (jamais la couleur seule : règle 16). */
export function Pastille({ couleur = "gris", children, icone: Icone }) {
  const c = { vert: "bg-emerald-100 text-emerald-800", rouge: "bg-rose-100 text-rose-800", orange: "bg-orange-100 text-orange-800",
              bleu: "bg-sky-100 text-emeraude", gris: "bg-slate-100 text-slate-700", violet: "bg-violet-100 text-violet-800" }[couleur];
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${c}`}>{Icone && <Icone size={13} />}{children}</span>;
}
