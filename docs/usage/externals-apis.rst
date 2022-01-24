=============
External APIs
=============

Geotrek et IGNrando'
====================

Depuis la version 0.32.0, Geotrek-admin est capable de produire un flux des itinéraires et POIs présents dans sa BDD au format Cirkwi pour pouvoir les importer directement dans IGNrando'.

Exemple des randonnées et POIs du Parc national des Ecrins publiées sur IGNrando' depuis Geotrek-admin : https://ignrando.fr/fr/communautes/parc-national-des-ecrins

Depuis cette version, 2 flux sont automatiquement générés par Geotrek-admin au format attendu par l'IGN :

- [URL_GEOTREK-ADMIN]/api/cirkwi/circuits.xml
- [URL_GEOTREK-ADMIN]/api/cirkwi/pois.xml

Il est possible d'exclure les POI du flux pour ne diffuser que les randonnées. Pour cela, ajouter le paramètre ``?withoutpois=1`` à la fin de l'URL (``http://XXXXX/api/cirkwi/circuits.xml?withoutpois=1``).

Il est possible de filtrer les POI du flux par structure. Pour cela, ajouter le paramètre ``?structures=<identifiant_de_la_structure>`` à la fin de l'URL (``http://XXXXX/api/cirkwi/pois.xml?structures=2``).
Vous pouvez filtrer avec plusieurs structures : en séparant les identifiants par des virgules (``http://XXXXX/api/cirkwi/pois.xml?structures=2,5,3``).

Il est également possible de filtrer les randonnées du flux par structure et par portail. Pour cela, ajouter le paramètre ``?structures=<identifiant_de_la_structure>``.
ou ``?portals=<identifian_de_la_structure>`` à la fin de l'URL (``http://XXXXX/api/cirkwi/circuits.xml?portals=3``).
Tout comme les pois Vous pouvez filtrer avec plusieurs structures et portails : en séparant les identifiants par des virgules.

Il est possible de filtrer les randonnées par portail et structure en même temps en séparant les 2 filtres par un ``&`` (``http://XXXXX/api/cirkwi/circuits.xml?portals=3&structures=1``).

Le référentiel CIRKWI a été intégré dans 3 tables accessibles dans l'Adminsite (à ne pas modifier) :

.. image :: /images/user-manual/cirkwi-tables.png

Si vous ne souhaitez pas utiliser les valeurs par défaut ou avez créez vos propres typologies, il faut que vous renseigniez les correspondances entre les catégories de votre Geotrek et celles du référentiel IGN (Cirkwi) dans votre Adminsite. Comme indiqué ici : https://github.com/GeotrekCE/Geotrek-admin/issues/806.

* Pratique >> locomotion/loisirs
* Accessibilite >> thematiques/tags
* Themes >> thematiques/tags
* Types de POI >> Categories POI

Les correspondances avec les valeurs de ces 3 tables sont donc à renseigner dans les tables Geotrek des Pratiques, Accessibilités, Thèmes et Types de POI.

Ce même flux est aussi utilisable pour alimenter directement la plateforme Cirkwi : https://pro.cirkwi.com/importez-vos-donnees-geotrek-dans-cirkwi/.

:Note:

    Geotrek-admin dispose aussi d'une API générique permettant d'accéder aux contenus d'une instance à l'adresse : ``[URL_GEOTREK-ADMIN]/api/v2/``
