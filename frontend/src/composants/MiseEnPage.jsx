// Cadre du portail : barre du haut (auto-école de travail), barre latérale bleu nuit (menus à pictogrammes, élément actif orange, pastilles),
// menu replié derrière « Menu » sur téléphone. Majuscule à chaque mot (règle 18).
import { MessageCircle, Star, Car, Package, ArrowLeftRight, CalendarCheck, BarChart3, Building2, ClipboardList, GraduationCap, LayoutDashboard, LogOut, Menu, Receipt, ShieldCheck, Tag, UserCog, Wallet, X, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useApp } from "../lib/contexte.jsx";
import { titreMenu } from "../lib/format.js";
import BandeauVersion from "./BandeauVersion.jsx";
import Logo from "./Logo.jsx";

// Chaque entrée : chemin, libellé, pictogramme, rôles autorisés (liste vide = tous), `ecole` = nécessite une auto-école de travail.
const TOUS_ECOLE = ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable", "moniteur"];
const MENU = [
  { chemin: "/", libelle: "tableau de bord", icone: LayoutDashboard, roles: ["super_admin", "directeur", "gestionnaire", "comptable"], ecole: true },
  { chemin: "/eleves", libelle: "élèves", icone: GraduationCap, roles: TOUS_ECOLE, ecole: true },
  { chemin: "/examens", libelle: "examens", icone: CalendarCheck, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable", "moniteur"], ecole: true },
  { chemin: "/transferts", libelle: "transferts de dossiers", icone: ArrowLeftRight, roles: ["super_admin", "directeur", "gestionnaire"], ecole: true },
  { chemin: "/statistiques", libelle: "statistiques d'examens", icone: BarChart3, roles: ["super_admin", "directeur", "gestionnaire", "comptable"], ecole: true },
  { chemin: "/parc", libelle: "parc automobile", icone: Car, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable", "moniteur", "mecanicien"], ecole: true },
  { chemin: "/pieces", libelle: "pièces et approvisionnement", icone: Package, roles: ["super_admin", "directeur", "gestionnaire", "mecanicien"], ecole: true },
  { chemin: "/messagerie", libelle: "centre de messagerie WA", icone: MessageCircle, roles: ["super_admin", "directeur", "gestionnaire", "secretaire"], ecole: true },
  { chemin: "/avis", libelle: "évaluations des clients", icone: Star, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable"], ecole: true },
  { chemin: "/caisse", libelle: "caisse et paiements", icone: Wallet, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable"], ecole: true },
  { chemin: "/impayes", libelle: "impayés", icone: Receipt, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable"], ecole: true },
  { chemin: "/tarifs", libelle: "tarifs et promotions", icone: Tag, roles: ["super_admin", "directeur", "gestionnaire", "secretaire", "comptable", "moniteur"], ecole: true },
  { chemin: "/ecoles", libelle: "auto-écoles", icone: Building2, roles: ["super_admin"] },
  { chemin: "/parametres", libelle: "paramètres de l'école", icone: MapPin, roles: ["super_admin", "directeur"], ecole: true },
  { chemin: "/comptes", libelle: "gestion des comptes", icone: UserCog, roles: ["super_admin", "directeur"] },
  { chemin: "/journal", libelle: "journal d'audit", icone: ClipboardList, roles: ["super_admin", "directeur"] },
  { chemin: "/compte", libelle: "mon compte", icone: ShieldCheck, roles: [] },
];

export default function MiseEnPage() {
  const { utilisateur, deconnecter, ecoles, ecoleChoisie, choisirEcole, parametres, compteurs } = useApp();
  const { pathname } = useLocation();
  const [ouvert, setOuvert] = useState(false);
  useEffect(() => setOuvert(false), [pathname]);
  const entrees = MENU.filter((m) => m.roles.length === 0 || m.roles.includes(utilisateur.role));
  // Le super administrateur sans école choisie n'accède qu'aux pages « Auto-écoles », « Comptes », « Journal » et « Mon compte ».
  const sansEcole = utilisateur.plateforme && !ecoleChoisie;
  const pageLibre = ["/ecoles", "/comptes", "/journal", "/compte"].some((p) => pathname.startsWith(p));
  return (
    <>
      {/* BARRE DU HAUT : l'auto-école de travail, tout en haut de chaque écran (liste pour le super administrateur, nom imposé pour les autres) */}
      <header className="sticky top-0 z-50 flex h-12 items-center gap-3 bg-white px-4 shadow-sm ring-1 ring-encre/10" data-testid="barre-ecole">
        <Building2 size={20} className="text-citron" aria-hidden="true" />
        <span className="hidden text-[11px] font-semibold uppercase tracking-wider text-ardoise sm:inline">Auto-école</span>
        {utilisateur.plateforme ? (
          <select value={ecoleChoisie} onChange={(e) => choisirEcole(e.target.value)} aria-label="Auto-école de travail" data-testid="selecteur-ecole"
            className="min-w-0 max-w-[60vw] rounded-lg border border-encre/15 bg-brume px-3 py-1.5 text-sm font-semibold text-encre focus:outline-none focus:ring-2 focus:ring-citron">
            <option value="">— Choisir une auto-école —</option>
            {ecoles.filter((c) => c.actif).map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
          </select>
        ) : <span className="truncate text-sm font-semibold text-encre" data-testid="nom-ecole">{parametres?.nom || utilisateur.ecole_nom}</span>}
        {sansEcole && <span className="hidden text-xs font-semibold text-orange-700 sm:inline">Choisissez l'auto-école où vous travaillez</span>}
      </header>
      <div className="min-h-[calc(100vh-3rem)] overflow-x-clip md:grid md:grid-cols-[230px_1fr]">
        <aside className="barre-laterale sticky top-12 z-40 flex max-h-[calc(100vh-3rem)] flex-col gap-1 overflow-y-auto bg-encre p-4 text-white md:h-[calc(100vh-3rem)] md:overscroll-contain">
          <div className="flex items-center justify-between px-2 md:mb-4">
            <Logo clair />
            <button type="button" onClick={() => setOuvert((o) => !o)} aria-expanded={ouvert} aria-controls="menu-portail"
              className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold text-white ring-1 ring-white/20 md:hidden">
              {ouvert ? <X size={18} /> : <Menu size={18} />}{ouvert ? "Fermer" : "Menu"}
            </button>
          </div>
          <nav id="menu-portail" className={`${ouvert ? "flex" : "hidden"} mt-3 flex-col gap-1 md:mt-0 md:flex`}>
            {entrees.map(({ chemin, libelle, icone: Icone }) => (
              <NavLink key={chemin} to={chemin} end={chemin === "/"}
                className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-1.5 text-sm font-semibold ${isActive ? "bg-white/10 text-citron" : "text-white/80 hover:bg-white/5 hover:text-white"}`}>
                <Icone size={18} className="shrink-0" /> <span className="min-w-0 flex-1">{titreMenu(libelle)}</span>
                {/* Pastille : nombre d'éléments à traiter (écrit : jamais la couleur seule), plafonné à 99+ */}
                {compteurs[chemin] > 0 && <span className="shrink-0 rounded-full bg-citron px-1.5 py-0.5 text-[11px] font-bold leading-none text-white" aria-label={`${compteurs[chemin]} à traiter`} data-testid={`pastille-${chemin.slice(1)}`}>{compteurs[chemin] > 99 ? "99+" : compteurs[chemin]}</span>}
              </NavLink>
            ))}
          </nav>
          <div className={`${ouvert ? "block" : "hidden"} mt-auto space-y-2 px-2 pt-6 text-xs text-white/60 md:block`}>
            <p className="truncate font-semibold text-white/85">{utilisateur.nom}</p>
            <span className="inline-block rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-citron">{utilisateur.role_libelle}</span>
            <button type="button" onClick={deconnecter} className="flex items-center gap-2 font-semibold text-white/80 hover:text-white"><LogOut size={14} /> Se déconnecter</button>
            <BandeauVersion className="!text-white/50" />
          </div>
        </aside>
        {/* key = école : changer d'école recharge entièrement la page (aucune donnée de l'ancienne école ne reste à l'écran) */}
        <main key={ecoleChoisie || "aucune"} className="min-w-0 p-4 sm:p-6 lg:p-8">
          {sansEcole && !pageLibre ? (
            <div className="mx-auto mt-10 max-w-md rounded-2xl bg-white p-6 text-center ring-1 ring-encre/5">
              <Building2 size={40} className="mx-auto text-citron" />
              <h1 className="mt-3 text-xl font-semibold">Choisissez une auto-école</h1>
              <p className="mt-2 text-sm text-ardoise">Choisissez l'auto-école où vous travaillez dans la liste « Auto-école » en haut de l'écran, ou créez-en une dans « Auto-écoles ».</p>
            </div>
          ) : <Outlet />}
        </main>
      </div>
    </>
  );
}
