/* Pixel Meta — mesure des publicites Skillora.
   ============================================
   Charge une seule fois, sur toutes les pages publiques et dans l'app.

   POURQUOI PLUS QUE « PageView »
   Un pixel qui ne compte que les visites ne sert qu'au reciblage. Ce qui fait
   baisser le cout d'acquisition, c'est de dire a Meta QUI est alle au bout :
   inscription terminee, abonnement pris. Meta apprend alors a chercher des
   gens qui ressemblent a ceux-la, au lieu de chercher des clics.

   Les evenements sont declenches depuis le code de l'app, aux vrais moments :
     - CompleteRegistration -> le questionnaire d'inscription est termine ;
     - Subscribe            -> l'abonnement Pro devient actif ;
     - CopieLancee (custom) -> la personne lance sa premiere copie.

   TOUT EST FACULTATIF : si un bloqueur de publicite empeche le chargement,
   `fbq` reste une file d'attente vide et rien ne casse. Aucun appel n'est
   jamais fait sans passer par les fonctions ci-dessous, qui avalent les
   erreurs. */
(function () {
  var ID = '1816149169379314';

  /* Code officiel Meta (ne pas modifier) */
  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
  n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,
  document,'script','https://connect.facebook.net/en_US/fbevents.js');

  try {
    fbq('init', ID);
    fbq('track', 'PageView');
  } catch (e) { /* pixel indisponible : le site continue normalement */ }

  /* Evenement standard Meta (CompleteRegistration, Subscribe, Purchase…). */
  window.skPixel = function (nom, params) {
    try { if (typeof fbq === 'function') fbq('track', nom, params || {}); }
    catch (e) {}
  };

  /* Evenement a nous (n'existe pas dans la liste Meta). */
  window.skPixelPerso = function (nom, params) {
    try { if (typeof fbq === 'function') fbq('trackCustom', nom, params || {}); }
    catch (e) {}
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
