// Copie chaque vente payée sur la page Truflame dans Shopify (commande « payée ») :
// Shopify prévient le propriétaire et AutoDS peut la passer chez le fournisseur.
// Clés : app du Dev Dashboard installée sur la boutique (client credentials, jeton de 24 h).
const SHOP = process.env.SHOPIFY_SHOP || 'kiibxq-yn';
const VARIANTE = 'gid://shopify/ProductVariant/67855270150434';
const VERSION = '2026-07';
let jeton = null, expire = 0;

const actif = () => !!(process.env.SHOPIFY_CLIENT_ID && process.env.SHOPIFY_CLIENT_SECRET);

async function getToken() {
  if (jeton && Date.now() < expire - 60000) return jeton;
  const r = await fetch(`https://${SHOP}.myshopify.com/admin/oauth/access_token`, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'client_credentials', client_id: process.env.SHOPIFY_CLIENT_ID, client_secret: process.env.SHOPIFY_CLIENT_SECRET }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new Error('jeton Shopify ' + r.status + ' ' + JSON.stringify(j).slice(0, 200));
  jeton = j.access_token; expire = Date.now() + (Number(j.expires_in) || 86399) * 1000;
  return jeton;
}

async function gql(query, variables) {
  const r = await fetch(`https://${SHOP}.myshopify.com/admin/api/${VERSION}/graphql.json`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': await getToken() },
    body: JSON.stringify({ query, variables }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || (j.errors && j.errors.length)) throw new Error('Shopify ' + r.status + ' ' + JSON.stringify(j.errors || j).slice(0, 300));
  return j.data;
}

const CREER = `mutation($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) { order { id name } userErrors { field message } } }`;

// v = { orderID, captureID, qty, montant ('59.48'), email, nom, adresse (PayPal), test }
async function creerCommande(v) {
  if (!actif()) return null;
  const a = v.adresse || {};
  const mots = String(v.nom || '').trim().split(/\s+/);
  const adresse = {
    firstName: mots.length > 1 ? mots.slice(0, -1).join(' ') : mots[0] || '', lastName: mots.length > 1 ? mots[mots.length - 1] : '',
    address1: a.address_line_1 || '', address2: a.address_line_2 || '', city: a.admin_area_2 || '',
    provinceCode: a.admin_area_1 || undefined, zip: a.postal_code || '', countryCode: a.country_code || undefined,
    phone: v.phone || undefined,
  };
  const argent = (x) => ({ shopMoney: { amount: x, currencyCode: 'USD' } });
  const unite = (Number(v.montant) / v.qty).toFixed(2);
  const order = {
    email: v.email || undefined, currency: 'USD', financialStatus: 'PAID',
    lineItems: [{ variantId: v.variantId || VARIANTE, quantity: v.qty, priceSet: argent(unite) }],
    shippingAddress: adresse, billingAddress: adresse,
    shippingLines: [{ title: 'Free shipping', priceSet: argent('0.00') }],
    transactions: [{ kind: 'SALE', status: 'SUCCESS', gateway: v.passerelle || 'PayPal', authorizationCode: v.captureID || v.orderID, amountSet: argent(v.montant) }],
    sourceName: v.source || 'truflame-page', sourceIdentifier: v.orderID, note: (v.passerelle || 'PayPal') + ' ' + v.orderID + (v.test ? ' · TEST 1 $ (à rembourser, ne pas envoyer)' : ''),
    tags: [ 'truflame', String(v.passerelle || 'paypal').toLowerCase() ].concat(v.test ? ['TEST'] : []),
  };
  const options = { sendReceipt: !v.test, sendFulfillmentReceipt: true, inventoryBehaviour: 'BYPASS' };
  let d = await gql(CREER, { order, options });
  if (d.orderCreate.userErrors.length) {   // état / région refusés hors US : on réessaie sans le code de région
    console.error('orderCreate', JSON.stringify(d.orderCreate.userErrors));
    delete order.shippingAddress.provinceCode; order.billingAddress = order.shippingAddress;
    d = await gql(CREER, { order, options });
    if (d.orderCreate.userErrors.length) throw new Error(JSON.stringify(d.orderCreate.userErrors).slice(0, 300));
  }
  return d.orderCreate.order;
}

async function verifier() {   // test de la clé, sans rien modifier
  if (!actif()) return { shopify: 'cles absentes' };
  const d = await gql('{ shop { name } }');
  return { shopify: 'ok', boutique: d.shop.name };
}

module.exports = { creerCommande, actif, verifier };
