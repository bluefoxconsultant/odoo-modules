# bf_cx_mass_mailing : exclusion des boucles ouvertes

S'auto-installe quand `bf_cx` et `mass_mailing` sont installés. Ajoute
aux envois de masse une case « Exclure les boucles CX ouvertes »
(décochée par défaut) : à l'envoi, les destinataires dont le contact a
un feedback à rappeler non traité ou une plainte ouverte sont retirés
de la liste (appariement par courriel normalisé, listes de diffusion et
contacts couverts). Aucun envoi nouveau ; sans l'option, comportement
standard inchangé.
