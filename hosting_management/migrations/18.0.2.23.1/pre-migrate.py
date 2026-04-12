def migrate(cr, version):
    # Rename demo-server xmlid to avoid leaking internal naming convention.
    # Preserves the existing record binding so the user's customized hosting.server
    # row isn't duplicated when data/hosting_server_data.xml creates the new xmlid.
    cr.execute("""
        UPDATE ir_model_data
        SET name = 'server_prod1'
        WHERE module = 'hosting_management' AND name = 'server_primetime1'
    """)
