Ce dépôt regroupe les outils pour gérer et publier le programme des cinémas du Morvan.

Il contient deux parties complémentaires. La première est un parser de programme qui transforme des données sources (listings de séances) en un format JSON propre et homogène. Ce JSON sert de source unique de vérité et peut être facilement mis à jour ou régénéré.

La seconde partie est un site web statique qui consomme ce JSON et permet de consulter le programme par cinéma, par date ou par film. Le site fonctionne entièrement côté client, sans backend, et peut être déployé gratuitement sur Netlify, GitHub Pages ou un service équivalent. Chaque film inclut des liens vers des aperçus (bandes-annonces via recherche YouTube) et des pages d’information (Allociné).

L’objectif du projet est de rester volontairement simple, transparent et durable : données lisibles, aucune dépendance lourde, hébergement gratuit et maintenance minimale.