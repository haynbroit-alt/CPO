# SIOS — Vision finale

**En une phrase :** SIOS devient le standard de la preuve d'économies vérifiable — l'artefact qu'une entreprise génère pour prouver, à un tiers, exactement combien elle a récupéré. Pas un outil d'audit de plus. Une **unité de confiance portable** dans la finance des PME.

---

## Le produit final n'est pas le rapport. C'est le CPO.

Aujourd'hui le CPO est une feature dans le README. Dans la vision finale, c'est l'objet central — tout le reste gravite autour. Un CPO, c'est une preuve content-addressée, reproductible, signée : *« voici une fuite de 1 195 €, voici la donnée qui le prouve, re-vérifie toi-même. »*

Le jour où ce format devient ce qu'un comptable, un vendeur SaaS ou un CFO *attend* de recevoir — comme on attend une facture PDF ou un lien Calendly — il n'y a plus un produit, il y a un protocole. C'est ça, « faire sa place tout seul » : devenir le format par défaut d'une transaction qui existait déjà mais qui n'avait pas de standard.

---

## La boucle qui se propulse

C'est la seule chose qui compte vraiment.

Une entreprise passe SIOS, trouve un doublon Datadog. Pour se faire rembourser, son geste *naturel et obligé* est d'envoyer la preuve à Datadog. Cette preuve porte le lien verify SIOS — chez un destinataire qui n'est pas client, qui voit un format propre, vérifiable, et se demande « c'est quoi ce truc ».

**L'acte de récupérer son argent est l'acte de diffuser le produit.**

Le destinataire d'aujourd'hui est le prospect de demain. Aucune autre catégorie d'outil n'a ça : la motivation de l'utilisateur (récupérer du cash) et le mécanisme de croissance (partager la preuve) sont **le même geste**. On ne paie pas pour acquérir — l'utilisateur acquiert pour nous parce que ça le sert.

---

## Le multiplicateur structurel : le comptable

La boucle de partage diffuse horizontalement (d'entreprise à vendeur). Le comptable diffuse *verticalement* : un cabinet a 50 à 200 clients. SIOS devient son service à facturer — il passe l'audit, encaisse sa marge, et chaque client audité génère ses propres CPO partagés.

Un comptable convaincu = un canal de distribution entier qui s'active sans nous. Dans la vision finale, SIOS n'a pas une force de vente. Il a un réseau de cabinets qui le déploient parce que ça leur rapporte.

---

## Le fossé (moat)

Trois couches qui se renforcent :

1. **La proof gallery réelle** — à mesure que les vrais recouvrements s'accumulent, la preuve sociale devient infalsifiable et impossible à rattraper pour un copieur parti de zéro.
2. **L'effet de réseau du format** — plus de gens reconnaissent et font confiance au CPO, plus en émettre a de valeur. Bénéfice classique du standard.
3. **La donnée d'inefficacité** — chaque audit affine les détecteurs et les baselines par secteur. Un nouvel entrant a le code ; il n'a ni les preuves, ni le réseau, ni la donnée.

---

## La catégorie que ça crée

On ne se bat pas dans « outils d'analyse de dépenses » (encombré). On crée « la preuve d'économies vérifiable » — la réponse à une question que personne n'outille proprement :

*Non pas « où est-ce que je gaspille ? » mais « comment je prouve à un tiers ce que j'ai récupéré, sans qu'il me croie sur parole ? »*

Détecter, beaucoup le font. **Prouver de façon reproductible et partageable, personne.** C'est l'angle propriétaire, et il est défendable.

---

## La trajectoire

| Phase | Signal | Levier |
|-------|--------|--------|
| **Amorce** | 10–15 audits réels, un secteur précis | Manuel. Toujours. |
| **Boucle** | Les proof cards et liens verify circulent | Les premiers vrais recouvrements remplissent la galerie |
| **Multiplicateur** | 3–5 cabinets comptables adoptent SIOS | Distribution verticale sans force de vente |
| **Standard** | Connecteurs Qonto / Pennylane / QuickBooks, API | Le CPO devient un format attendu |
| **Infrastructure** | D'autres SaaS embarquent le format | SIOS est la couche de preuve, pas l'outil |

---

## Niveaux — où on est, où on va

La vision cible est ⭐⭐⭐⭐⭐ partout. L'état actuel, évalué honnêtement sur le dépôt tel qu'il est :

| Niveau | Actuel | Vision cible | Ce qui ferme l'écart |
|--------|--------|--------------|----------------------|
| **Vision** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | La vision est écrite, focalisée, AXIOM parqué. La 5ᵉ étoile ne s'écrit pas — elle se gagne quand un tiers (client, comptable, vendeur) la valide par ses actes. |
| **Architecture** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Le paquet `sios/` est modulaire (core, connectors, proof_layer, api), mais l'ancien `app/` et `axiom/` coexistent encore. Supprimer le legacy, un seul chemin de code. |
| **Code** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~7 000 lignes, CI en place, 30 tests verts — mais 12 tests legacy cassés sur l'ancien module. Nettoyer, couvrir le proof layer, zéro test rouge toléré. |
| **Infrastructure** | ⭐⭐ | ⭐⭐⭐⭐⭐ | Render plan gratuit, Docker, CI. Il manque : monitoring, sauvegardes du store, environnement de staging, et une URL verify qui ne peut jamais tomber — c'est la crédibilité du format. |
| **Produit** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | La boucle existe de bout en bout : CLI → CPO → page verify → paiement 49 €. Mais elle n'a pas encore été traversée par un utilisateur réel. La boucle de partage doit être vécue, pas seulement câblée. |
| **Traction** | ⭐ | ⭐⭐⭐⭐⭐ | La galerie est remplie de données anonymisées de démonstration. Zéro recouvrement réel documenté. Tout commence ici : 10–15 audits manuels, un secteur, des vraies preuves. |

Les niveaux ne se remplissent pas dans n'importe quel ordre : **Traction tire tout le reste.** Un seul recouvrement réel vaut plus qu'une étoile de plus sur chacune des autres lignes.

---

## L'honnêteté qui fait tenir la vision

**AXIOM n'en fait pas partie.** Le protocole d'allocation de capital aux agents est une *autre* vision, plus grande, et c'est exactement ce qui la rend dangereuse maintenant — elle dilue celle-ci. Parquée, datée, on y revient quand SIOS gagne de l'argent.

La preuve d'économies est un endgame suffisant pour être immense.

---

*Pas un produit qu'on pousse — un **standard de preuve qui se propage parce que l'utiliser, c'est le diffuser.***
