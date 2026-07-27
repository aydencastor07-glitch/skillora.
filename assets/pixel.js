/* Pixel Meta — mesure des publicites Skillora, en configuration MAXIMALE.
   =====================================================================
   Charge sur toutes les pages publiques et dans l'app.

   TROIS NIVEAUX, ET ILS COMPTENT TOUS
   -----------------------------------
   1. LES EVENEMENTS. Un pixel qui ne compte que les visites ne sert qu'au
      reciblage : Meta continue de chercher des CLICS. On lui envoie donc les
      etapes qui comptent vraiment — inscription terminee, abonnement pris —
      pour qu'il aille chercher des gens qui vont jusqu'au bout.

   2. LA CORRESPONDANCE AVANCEE (le plus gros levier). Sans elle, Meta ne
      relie qu'une partie des inscriptions a la personne qui a vu la pub : le
      reste est perdu, et les chiffres sous-estiment le resultat reel. En lui
      transmettant de quoi reconnaitre la personne, le taux de correspondance
      monte fortement — donc l'optimisation devient bien plus juste.
      Le navigateur CHIFFRE ces informations (SHA-256) AVANT tout envoi :
      Meta ne recoit jamais l'email en clair, seulement une empreinte.

   3. L'IDENTIFIANT D'EVENEMENT. Chaque evenement porte un identifiant unique.
      C'est ce qui permettra, quand l'API Conversions sera branchee, d'envoyer
      le meme evenement depuis le serveur SANS le compter deux fois.

   TOUT EST FACULTATIF : si un bloqueur empeche le chargement, `fbq` reste une
   file d'attente vide, les appels sont avales et le site fonctionne pareil. */
(function () {
  var ID = '1816149169379314';

  /* Code officiel Meta (ne pas modifier) */
  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
  n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
  document,'script','https://connect.facebook.net/en_US/fbevents.js');

  var identite = null;   // renseignee des qu'on connait la personne connectee

  function init() {
    try {
      if (identite) fbq('init', ID, identite);
      else fbq('init', ID);
    } catch (e) {}
  }
  init();
  try { fbq('track', 'PageView'); } catch (e) {}

  /* Identifiant unique par evenement — indispensable pour ne jamais compter
     deux fois le meme evenement quand il arrive par deux chemins. */
  function idEvenement() {
    try {
      var t = new Uint8Array(9);
      (window.crypto || window.msCrypto).getRandomValues(t);
      return Date.now().toString(36) + '-' +
        Array.from(t).map(function (x) { return x.toString(36); }).join('');
    } catch (e) {
      return Date.now().toString(36) + '-' + String(Math.random()).slice(2, 12);
    }
  }

  /* ── CORRESPONDANCE AVANCEE ────────────────────────────────────────────
     A appeler des qu'on sait qui est connecte. Le SDK Meta normalise puis
     CHIFFRE chaque valeur avant l'envoi : rien ne part en clair.
     `external_id` est notre identifiant interne — il ne dit rien de la
     personne a lui seul, mais il permet a Meta de recoller les visites d'un
     meme compte entre deux appareils. */
  window.skPixelIdentite = function (u) {
    if (!u) return;
    try {
      var d = {};
      if (u.email)      d.em = String(u.email).trim().toLowerCase();
      if (u.id)         d.external_id = String(u.id);
      var nom = String(u.name || '').trim();
      if (nom) {
        var m = nom.split(/\s+/);
        d.fn = m[0].toLowerCase();
        if (m.length > 1) d.ln = m[m.length - 1].toLowerCase();
      }
      if (u.country) d.country = String(u.country).trim().toLowerCase();
      if (!Object.keys(d).length) return;
      // Rien de nouveau ? on ne re-initialise pas pour rien.
      var sig = JSON.stringify(d);
      if (identite && JSON.stringify(identite) === sig) return;
      identite = d;
      init();          // Meta met a jour la correspondance avancee
    } catch (e) {}
  };

  /* Evenement standard Meta (CompleteRegistration, Subscribe, Purchase…). */
  window.skPixel = function (nom, params) {
    try {
      if (typeof fbq !== 'function') return;
      fbq('track', nom, params || {}, { eventID: idEvenement() });
    } catch (e) {}
  };

  /* Evenement a nous (n'existe pas dans la liste Meta). */
  window.skPixelPerso = function (nom, params) {
    try {
      if (typeof fbq !== 'function') return;
      fbq('trackCustom', nom, params || {}, { eventID: idEvenement() });
    } catch (e) {}
  };

  /* Certains evenements ne doivent partir QU'UNE FOIS par personne : une
     inscription comptee deux fois fausse le cout par inscription, et Meta
     optimise alors sur des chiffres qui n'existent pas. */
  window.skPixelUneFois = function (cle, nom, params) {
    try {
      var k = 'sk_px_' + cle;
      if (localStorage.getItem(k)) return;
      localStorage.setItem(k, '1');
    } catch (e) { /* stockage inaccessible : on envoie quand meme */ }
    window.skPixel(nom, params);
  };
})();
