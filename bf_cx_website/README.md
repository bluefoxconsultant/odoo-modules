# bf_cx_website : témoignages publics

S'auto-installe quand `bf_cx` et `website` sont installés. Publie la
page publique `/temoignages`, qui rend dynamiquement les témoignages
en état « Publié » (citation, nom du client, société du client),
filtrés sur la société du site web courant. Aucun envoi client, aucun
menu de site ajouté : le propriétaire du site décide où lier l'URL
`/temoignages`.

Conformité Loi 25 : un témoignage retiré (état autre que « Publié »)
disparaît instantanément du site puisque le rendu est dynamique.
