# Programme cinéma (statique)

Site web 100 % statique pour consulter un programme cinéma par cinéma, par date ou par film, avec recherche, filtres VF/VOST et liens d’aperçu.

Ce site fonctionne en `file://` sans CORS car il utilise des scripts classiques (pas d’import ES modules). Si vous souhaitez revenir aux modules ES, lancez un petit serveur local.

## Comment modifier les données

1) Ouvrir `data.js`.
2) Remplacer ou compléter le tableau `PROGRAM`.
3) Recharger `index.html` dans le navigateur.

Le format attendu est :

```js
{
  cinema: "Nom du cinéma",
  movie_title: "Titre du film",
  date: "YYYY-MM-DD",
  time: "20h30",
  version: "VF" // ou "VOST"
}
```

## Déployer sur Netlify

1) Ouvrir Netlify.
2) Glisser-déposer le dossier contenant `index.html`, `styles.css`, `app.js`, `data.js`.
3) Netlify détecte automatiquement un site statique et publie l’URL.

## Déployer sur GitHub Pages

1) Pousser ce dossier dans un repo GitHub.
2) Dans GitHub : Settings → Pages.
3) Sélectionner la branche (ex : `main`) et le dossier racine `/`.
4) Enregistrer : l’URL publique est affichée après quelques secondes.

## Liens d’aperçu

Les liens “Aperçu” pointent vers une recherche YouTube (bande annonce) et “Allociné” vers une recherche Allociné. Ils ne nécessitent aucune API ni clé.
