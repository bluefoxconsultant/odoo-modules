{
    "name": "BF Recherche universelle",
    "version": "18.0.1.3.0",
    "category": "Productivity",
    "summary": "Recherche transversale dans tous les modules via la palette de commandes",
    "author": "Blue Fox Inc",
    "website": "https://example.com",
    "license": "Other OSI approved licence",
    "depends": ["web", "base"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_universal_search/static/src/scss/universal_search.scss",
            "bf_universal_search/static/src/js/universal_search_provider.js",
            "bf_universal_search/static/src/js/universal_search_systray.js",
            "bf_universal_search/static/src/xml/universal_search.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
