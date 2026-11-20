// Page PUBLIQUE d'évaluation (sans compte) : ouverte par le lien personnel reçu par WhatsApp ; une seule réponse par lien. Pensée pour le téléphone.
import { Send } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Bouton from "../composants/Bouton.jsx";
import { Case } from "../composants/Champs.jsx";
import Logo from "../composants/Logo.jsx";
import { api } from "../lib/api.js";

/** Cinq étoiles cliquables (boutons accessibles, valeur écrite : jamais la couleur seule). */
function Etoiles({ valeur, onChange, libelle }) {
  return (
    <div role="radiogroup" aria-label={libelle} className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((n) => <button key={n} type="button" role="radio" aria-checked={valeur === n} aria-label={`${n} sur 5`} onClick={() => onChange(n)} className={`h-11 w-11 rounded-full text-2xl ${valeur >= n ? "text-citron" : "text-slate-300"} hover:bg-orange-50`}>★</button>)}
      {valeur > 0 && <span className="ml-1 text-sm text-ardoise">{valeur}/5</span>}
    </div>
  );
}

export default function AvisPublic() {
  const { jeton } = useParams();
  const [f, setF] = useState(null);
  const [erreur, setErreur] = useState("");
  const [r, setR] = useState({ note_globale: 0, nps: null, notes: {}, commentaire: "", autorise_publication: false });
  const [fini, setFini] = useState("");
  const [attente, setAttente] = useState(false);
  useEffect(() => { api(`/public/avis/${jeton}`, { avecJeton: false }).then(setF).catch((e) => setErreur(e.message)); }, [jeton]);
  const envoyer = () => { setAttente(true); api(`/public/avis/${jeton}`, { methode: "POST", avecJeton: false, corps: r }).then((x) => setFini(x.message)).catch((e) => setErreur(e.message)).finally(() => setAttente(false)); };
  return (
    <div className="min-h-dvh bg-brume px-4 py-8">
      <main className="mx-auto max-w-md rounded-3xl bg-white p-6 shadow-lg">
        <div className="flex justify-center"><Logo /></div>
        {!f && !erreur && <div className="py-10 flex justify-center"><span className="jauge" /></div>}
        {erreur && !fini && <p className="mt-6 text-center text-rose-700" role="alert">{erreur}</p>}
        {fini && <p className="mt-6 text-center text-lg font-semibold text-emeraude">{fini}</p>}
        {f && f.deja_repondu && !fini && <p className="mt-6 text-center">Vous avez déjà répondu : merci !</p>}
        {f && !f.deja_repondu && !fini && (<>
          <h1 className="mt-4 text-center font-editorial text-2xl font-bold italic">Votre avis nous intéresse</h1>
          <p className="mt-1 text-center text-sm text-ardoise">Bonjour {f.prenom}, merci d'avoir choisi <b>{f.ecole}</b>. Une minute suffit.</p>
          <p className="mt-5 font-semibold">Votre satisfaction globale *</p><Etoiles valeur={r.note_globale} onChange={(n) => setR({ ...r, note_globale: n })} libelle="Satisfaction globale" />
          <p className="mt-4 font-semibold">Recommanderiez-vous {f.ecole} à un proche ?</p>
          <div className="mt-1 flex flex-wrap gap-1" role="radiogroup" aria-label="Recommandation de 0 à 10">{Array.from({ length: 11 }, (_, n) => <button key={n} type="button" role="radio" aria-checked={r.nps === n} onClick={() => setR({ ...r, nps: n })} className={`h-10 w-10 rounded-full text-sm font-semibold ring-1 ring-encre/15 ${r.nps === n ? "bg-emeraude text-white" : "bg-white hover:bg-brume"}`}>{n}</button>)}</div>
          <p className="mt-1 flex justify-between text-xs text-slate-500"><span>0 = pas du tout</span><span>10 = absolument</span></p>
          <details className="mt-4"><summary className="cursor-pointer font-semibold">Détaillez par critère (facultatif)</summary>
            {f.criteres.map((c) => <div key={c.cle} className="mt-2"><p className="text-sm">{c.libelle}</p><Etoiles valeur={r.notes[c.cle] || 0} libelle={c.libelle} onChange={(n) => setR({ ...r, notes: { ...r.notes, [c.cle]: n } })} /></div>)}</details>
          <label className="mt-4 block text-sm font-semibold" htmlFor="com">Un commentaire ?</label>
          <textarea id="com" rows={3} maxLength={500} value={r.commentaire} onChange={(e) => setR({ ...r, commentaire: e.target.value })} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
          <div className="mt-2"><Case libelle={`J'autorise ${f.ecole} à publier mon avis (avec mon prénom seulement)`} valeur={r.autorise_publication} onChange={(x) => setR({ ...r, autorise_publication: x })} /></div>
          <Bouton icone={Send} variante="principal" attente={attente} disabled={!r.note_globale} onClick={envoyer} className="w-full">Envoyer mon avis</Bouton></>)}
      </main>
    </div>
  );
}
