# Veille Créative

Site de veille pour creative strategist : les **lead magnets** publiés par les agences (guides, templates, swipe files, banques de hooks, Notion, rapports gratuits). Mise à jour chaque jour, pour 0 €.

```
GitHub Actions (tous les jours à 5h UTC)
  → scripts/veille.py : collecte (détail ci-dessous)
  → lecture de chaque page (y compris les pages Notion) ; contenus payants écartés
  → tri par Gemini : uniquement des lead magnets, agences et français en priorité
  → data/ressources.json (commit automatique)
  → publication du site sur GitHub Pages (dans le même workflow)
```

## Ce qui est retenu

**Uniquement des lead magnets** : des ressources gratuites qu'une agence (en priorité), un freelance, un outil ou une marque offre pour attirer des prospects. Guides, livres blancs, templates, swipe files, banques de hooks ou d'angles, checklists, Notion, PDF, kits, rapports à télécharger. En accès libre, contre un email, ou via un post LinkedIn « commente et je t'envoie… ».

**Sont écartés** : articles de blog ou de média, actualités, posts de newsletter, études de cas, décryptages de campagnes, webinaires, offres payantes et **contenus réservés aux abonnés**.

Le périmètre se règle dans le champ `secteur` de `config.json`, transmis tel quel à l'IA.

## Priorité au français

La veille est francophone : l'anglais vient seulement en complément.
- **Recherches** : 75 % des requêtes sont en français (`priorite_francais`), avec l'option Tavily `country: france` qui favorise les résultats français.
- **Créateurs** : les agences et créateurs français sont explorés en premier.
- **Budget quotidien** : les candidats français sont analysés d'abord. L'anglais complète, avec au plus 1 candidat anglais pour 3 français.
- **Tri par l'IA** : un contenu français est publié à partir de 7/10 (`pertinence_min`), un contenu anglais seulement à partir de 8/10 (`pertinence_min_autres_langues`). L'IA ajoute aussi 1 point aux contenus français à qualité égale.
- **Sur le site** : les ressources françaises passent en premier à date ou note égale, les autres portent un badge `EN`, et le bouton « FR uniquement » masque tout ce qui n'est pas en français.

Titres, résumés et tags sont toujours rédigés en français, même pour une ressource en anglais.

## D'où viennent les ressources

Beaucoup de lead magnets, comme les pages Notion d'agences, **ne sont pas indexés par Google**. Ils circulent surtout sur LinkedIn. Le robot combine donc plusieurs sources :

| Source | Ce qu'elle apporte | Par jour |
|---|---|---|
| **Recherche tournante** | Combinaisons « format × sujet » (ex. « swipe file hooks vidéo », « PDF gratuit brief créatif ») sur Notion, Gumroad, Substack, Figma, Gamma, Google Docs… 300 combinaisons en français et 50 en anglais : chaque jour en teste **de nouvelles** | 9 FR + 3 EN |
| **Posts LinkedIn** | Posts « commente X et je t'envoie… », tels qu'indexés par le moteur de recherche, sans scraper LinkedIn | 5 FR + 1 EN |
| **Web ouvert** | Livres blancs, guides et rapports gratuits d'agences publiés dans les 30 derniers jours. `{annee_tendances}` vise l'année suivante à partir de septembre | 3 FR + 1 EN |
| **Exploration des agences** | Agences et créateurs français d'abord (Agence Short, AdsBack, Metalyde, Yann Le Mad, Roads, Takema, Noiise, Kickads, XPLR, We Are Social…), puis Motion, Foreplay, TikTok, Pinterest, et les sites des auteurs des lead magnets retenus | 8 sites |
| **Boule de neige** | Jusqu'à 5 liens vers d'autres ressources dans chaque page retenue | sans limite |
| **Soumissions** | Les liens que tu repères toi-même (sur LinkedIn par exemple) | sans limite |

Au total, cela fait 30 requêtes Tavily par jour, soit environ 900 par mois : on reste sous le quota gratuit de 1 000.

Les flux RSS de médias ont été retirés : ils apportaient surtout des articles. Tu peux en ajouter dans `flux_rss` (ex. une Google Alert ou la newsletter d'une agence qui partage ses ressources).

## Mise en ligne (15 minutes environ)

### 1. Créer les 2 clés API gratuites
- **Tavily** (recherche web) : crée un compte sur https://tavily.com, puis copie ta clé (`tvly-…`).
- **Gemini** (tri par IA) : va sur https://aistudio.google.com/apikey puis clique sur « Create API key ».

La clé Gemini est indispensable pour avoir une veille de qualité. Sans elle, le tri par mots-clés laisse passer beaucoup de pages génériques.

### 2. Mettre le projet sur GitHub
1. Crée un compte sur https://github.com, puis un **nouveau dépôt public**, par exemple `veille-creative`.
2. Clique sur « uploading an existing file » et glisse **tout le contenu de ce dossier**, y compris les dossiers cachés `.github` et `.nojekyll`. Sur Mac, `Cmd + Maj + .` affiche les fichiers cachés dans le Finder.

### 3. Ajouter les clés
Dans le dépôt, ouvre **Settings → Secrets and variables → Actions → New repository secret** et crée :
- `TAVILY_API_KEY`
- `GEMINI_API_KEY`

### 4. Activer le site
Ouvre **Settings → Pages → Build and deployment → Source : GitHub Actions**.
Le site sera en ligne à l'adresse `https://<ton-pseudo>.github.io/veille-creative/`. Il est republié après chaque veille, et dès que tu modifies un fichier du dépôt.

### 5. Lancer la première veille
Ouvre l'onglet **Actions**, choisis « Veille quotidienne », puis clique sur **Run workflow**.
Le journal affiche le nombre de résultats obtenus par source et la liste des ressources ajoutées. Ensuite, le workflow tourne seul chaque matin.

## Sur ton téléphone

Le site marche sur n'importe quel téléphone : ouvre simplement son adresse (`https://<ton-pseudo>.github.io/veille-creative/`).
Pour l'avoir comme une app, avec son icône et en plein écran :
- **iPhone** (Safari) : bouton **Partager** → **Sur l'écran d'accueil**.
- **Android** (Chrome) : menu **⋮** → **Ajouter à l'écran d'accueil** (ou **Installer l'application**).

Le robot tourne sur les serveurs de GitHub : ton Mac peut rester éteint, la veille se fait quand même chaque matin.

## Signets

Le bouton marque-page (sur chaque ligne et dans la fiche « Enregistrer ») garde les ressources importantes. Elles apparaissent dans la section **Mes signets** en haut du site, et le bouton **Signets** de la liste n'affiche qu'elles.

Les signets sont enregistrés **dans ton navigateur**, sans compte ni serveur. Ils restent donc sur l'appareil où tu les as créés : ceux de ton téléphone ne se retrouvent pas sur ton ordinateur, et vider les données du navigateur les efface.

## Ajouter des Google Alerts (recommandé, gratuit et illimité)
1. Va sur https://www.google.com/alerts et tape une requête, par exemple :
   - `site:notion.site hooks OR créas OR "static ads"`
   - `site:linkedin.com/posts "commente" hooks OR créas OR UGC`
   - `"trend report" OR "rapport tendances" social media`
   - `"tendances visuelles" OR "design trends"`
   - `"swipe file" ads`
2. Clique sur **Afficher les options → Envoyer à : Flux RSS → Créer l'alerte**.
3. Clique sur l'icône RSS de l'alerte, copie son adresse et ajoute-la dans `flux_rss.fr` (ou `flux_rss.en`) du fichier `config.json`.

Ajoute aussi les newsletters des agences et créateurs que tu suis : `https://nom.substack.com/feed`, ou le flux RSS d'une newsletter Beehiiv.

## Formulaire « Proposer une ressource » (facultatif)
1. Crée un Google Form avec une question « Lien de la ressource ».
2. Dans **Réponses → Lier à Sheets**, puis dans la feuille : **Fichier → Partager → Publier sur le web → format CSV**. Copie le lien obtenu.
3. Dans `config.json`, colle ce lien CSV dans `url_csv_soumissions` et le lien public du formulaire dans `site.formulaire_soumission`.

Astuce : garde le formulaire en favori sur ton téléphone. Quand tu vois passer un lead magnet sur LinkedIn, colle le lien : le robot l'analyse le lendemain et, en plus, explore le reste du site de son auteur.

## Personnaliser : `config.json`
| Clé | Rôle |
|---|---|
| `secteur` | Le périmètre de la veille, transmis à l'IA pour juger la pertinence |
| `categories` | Les filtres affichés sur le site |
| `priorite_francais` | La part des requêtes en français (0.75 = 75 %) |
| `pays_recherche_fr` | Le pays favorisé pour les recherches en français (`france`) |
| `pertinence_min` | La note minimale sur 10 pour publier un contenu en français (7 par défaut). Monte-la si le site se remplit trop |
| `pertinence_min_autres_langues` | La note minimale pour un contenu dans une autre langue (8 par défaut) |
| `recherche.fr` / `recherche.en` | Les formats et sujets combinés pour générer les recherches, par langue |
| `recherche.domaines_cibles` | Les plateformes où chercher (Notion, Gumroad…) |
| `linkedin.fr` / `linkedin.en` | Les recherches de posts LinkedIn, par langue |
| `web_ouvert.fr` / `web_ouvert.en` | Les recherches de tendances. `{annee}` et `{annee_tendances}` sont remplacés automatiquement |
| `createurs_a_suivre.fr` / `.en` | Les sites à explorer régulièrement (les français passent en premier) |
| `flux_rss.fr` / `flux_rss.en` / `filtre_rss` | Les flux à suivre et les mots-clés qu'un article doit contenir pour être analysé |
| `domaines_exclus` | Les sites à ignorer (correspondance exacte : `tiktok.com` n'exclut pas `ads.tiktok.com`) |
| `max_candidats_par_jour` | Le nombre maximum de liens analysés par jour (150 par défaut) |

## Fichiers de données
- `data/ressources.json` : les éléments publiés. Tu peux en ajouter ou en retirer directement depuis GitHub.
- `data/vus.json` : les liens déjà analysés et rejetés, pour ne pas les réanalyser. Si tu retires une ressource du site, ajoute ici son adresse sans `https://` ni `www.` (ex. `site.fr/guide`) pour qu'elle ne revienne pas.
- `data/createurs.json` : les sites de créateurs repérés et la date de leur dernière exploration.

## Tester en local
```bash
python3 scripts/veille.py --dry-run
python3 -m http.server 8000
```
Le premier teste la collecte sans rien enregistrer. Le second affiche le site sur http://localhost:8000.

## À savoir
- Les paliers gratuits de Tavily et Gemini peuvent évoluer : vérifie les quotas sur leurs sites.
- Le robot essaie plusieurs modèles Gemini gratuits (3.5 Flash, 3.5 Flash-Lite, 3.8 Flash…) et passe au suivant si Google en refuse un. Pour en imposer un, crée une variable (pas un secret) `GEMINI_MODEL` dans **Settings → Secrets and variables → Actions → Variables**.
- La lecture des pages Notion passe par l'API interne de notion.site. Elle n'est pas officielle et peut changer : dans ce cas, le robot se contente du titre et de l'extrait.
- Le site ne fait que référencer les ressources avec un lien : il ne copie pas leur contenu.
