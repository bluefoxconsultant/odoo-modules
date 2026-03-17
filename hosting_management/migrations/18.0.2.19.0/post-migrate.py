# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)



def _populate_existing_storage_configs(cr):
    """Populate storage_check_type and related fields on existing services."""

    # Container directory checks
    directory_configs = [
        # (code, path, docker_container_override)
        ("HST-0003", "/cryptpad/datastore", None),
        ("HST-0004", "/data", None),
        ("HST-0009", "/srv/data", None),
        ("HST-0012", "/data", "alvea-capital-vaultwarden"),
        ("HST-0018", "/var/www/html/data", None),
        ("HST-0019", "/data", "charles-groleau-vaultwarden"),
        ("HST-0025", "/var/www/html/data", None),
        ("HST-0029", "/data", "barbsvault-vaultwarden"),
        ("HST-0033", "/persist", None),
    ]

    for code, path, container_override in directory_configs:
        if container_override:
            cr.execute(
                """
                UPDATE hosting_service
                SET storage_check_type = 'container_directory',
                    storage_check_path = %s,
                    docker_container = %s
                WHERE code = %s
                """,
                (path, container_override, code),
            )
        else:
            cr.execute(
                """
                UPDATE hosting_service
                SET storage_check_type = 'container_directory',
                    storage_check_path = %s
                WHERE code = %s
                """,
                (path, code),
            )
        if cr.rowcount:
            _logger.info("Configured container_directory for %s", code)

    # PostgreSQL checks — docker_container MUST point to the DB container, not the app
    postgres_configs = [
        # (code, db_name, db_user, db_container)
        ("HST-0001", "blue-fox-inc", "blue-fox-inc", "blue-fox-inc-db"),
        ("HST-0011", "alvea-capital", "alvea-capital", "alvea-capital-db"),
        ("HST-0015", "vortex-solution", "vortex-solution", "vortex-solution-db"),
        ("HST-0017", "pme-conforme", "pme-conforme", "pme-conforme-db"),
    ]

    for code, db_name, db_user, db_container in postgres_configs:
        cr.execute(
            """
            UPDATE hosting_service
            SET storage_check_type = 'postgres',
                storage_check_db_name = %s,
                storage_check_db_user = %s,
                docker_container = %s
            WHERE code = %s
            """,
            (db_name, db_user, db_container, code),
        )
        if cr.rowcount:
            _logger.info("Configured postgres for %s", code)

    # Nextcloud DB checks — queries oc_filecache, auto-discovers credentials
    nc_db_configs = [
        # (code, db_container)
        ("HST-0002", "blue-fox-nc-db"),
        ("HST-0016", "ecolaction-nc-db"),
        ("HST-0024", "sylvie-rousseau-psychologue-nc-db"),
    ]

    for code, db_container in nc_db_configs:
        cr.execute(
            """
            UPDATE hosting_service
            SET storage_check_type = 'nextcloud_db',
                docker_container = %s
            WHERE code = %s
            """,
            (db_container, code),
        )
        if cr.rowcount:
            _logger.info("Configured nextcloud_db for %s", code)


def _create_new_services(cr, env):
    """Create new hosting.service records for previously untracked services."""

    # Helper to look up software by code
    def get_software_id(code):
        cr.execute("SELECT id FROM hosting_software WHERE code = %s", (code,))
        row = cr.fetchone()
        return row[0] if row else None

    # Helper to look up partner by name (partial match)
    def get_partner_id(name):
        cr.execute(
            "SELECT id FROM res_partner WHERE is_company = true AND name ILIKE %s LIMIT 1",
            (f"%{name}%",),
        )
        row = cr.fetchone()
        return row[0] if row else None

    # Helper to get server id (we only have PT1)
    cr.execute("SELECT id FROM hosting_server LIMIT 1")
    row = cr.fetchone()
    server_id = row[0] if row else None

    # Get user id for responsible (admin)
    cr.execute("SELECT id FROM res_users WHERE login = 'olivier@example.com' LIMIT 1")
    row = cr.fetchone()
    user_id = row[0] if row else SUPERUSER_ID

    # Software IDs
    sw_nc = get_software_id("NC")
    sw_od = get_software_id("OD")
    sw_ds = get_software_id("DS")
    sw_mst = get_software_id("MST")
    sw_mtx = get_software_id("MTX")
    sw_wz = get_software_id("WZ")
    sw_vw = get_software_id("VW")
    sw_n8n = get_software_id("N8N")

    # Partner IDs
    p_wildhome = get_partner_id("Wildhome")
    p_bluefox = get_partner_id("Blue Fox")
    p_pmeconforme = get_partner_id("PME Conforme")
    p_cpe_estrie = get_partner_id("CPE-Estrie") or get_partner_id("CPE Estrie")
    p_loisirshj = get_partner_id("Loisirs Henri-Julien") or get_partner_id("Henri-Julien")
    p_consentement = get_partner_id("Consentement") or get_partner_id("consentement")

    # New services to create
    # (name, software_id, partner_id, check_type, check_path, db_name, db_user,
    #  docker_container, s3_endpoint, s3_bucket, s3_access_key, s3_region, environment)
    new_services = []

    if sw_nc and p_wildhome:
        new_services.append({
            "name": "Nextcloud - Wildhome",
            "software_id": sw_nc,
            "partner_id": p_wildhome,
            "storage_check_type": "nextcloud_db",
            "docker_container": "wildhome-nc-db",
        })

    if sw_od and p_consentement:
        new_services.append({
            "name": "Odoo - Consentement Québec",
            "software_id": sw_od,
            "partner_id": p_consentement,
            "storage_check_type": "postgres",
            "docker_container": "consentement-quebec-db",
            "storage_check_db_name": "consentement-quebec",
            "storage_check_db_user": "consentement-quebec",
        })

    if sw_od and p_wildhome:
        new_services.append({
            "name": "Odoo - Wildhome",
            "software_id": sw_od,
            "partner_id": p_wildhome,
            "storage_check_type": "postgres",
            "docker_container": "wildhome-db",
            "storage_check_db_name": "wildhome",
            "storage_check_db_user": "wildhome",
        })
        new_services.append({
            "name": "Odoo - Wildhome CA",
            "software_id": sw_od,
            "partner_id": p_wildhome,
            "storage_check_type": "postgres",
            "docker_container": "wildhome-ca-db",
            "storage_check_db_name": "wildhome-ca",
            "storage_check_db_user": "wildhome-ca",
        })

    if sw_ds and p_cpe_estrie:
        new_services.append({
            "name": "Docuseal - CPE Estrie",
            "software_id": sw_ds,
            "partner_id": p_cpe_estrie,
            "storage_check_type": "postgres",
            "docker_container": "docuseal-cpe-estrie-db",
            "storage_check_db_name": "docuseal",
            "storage_check_db_user": "docuseal",
        })

    if sw_ds and p_loisirshj:
        new_services.append({
            "name": "Docuseal - Loisirs Henri-Julien",
            "software_id": sw_ds,
            "partner_id": p_loisirshj,
            "storage_check_type": "postgres",
            "docker_container": "docuseal-loisirshj-db",
            "storage_check_db_name": "docuseal",
            "storage_check_db_user": "docuseal",
        })

    if sw_mst and p_bluefox:
        new_services.append({
            "name": "Mastodon - Blue Fox",
            "software_id": sw_mst,
            "partner_id": p_bluefox,
            "storage_check_type": "host_directory",
            "storage_check_path": "/home/livv/mastodon-clients/blue-fox-mastodon/public/system",
        })

    if sw_mtx and p_bluefox:
        new_services.append({
            "name": "Matrix - Blue Fox",
            "software_id": sw_mtx,
            "partner_id": p_bluefox,
            "storage_check_type": "host_directory",
            "storage_check_path": "/home/livv/matrix/matrix-blue-fox/data/synapse",
        })

    if sw_wz and p_bluefox:
        new_services.append({
            "name": "Wazuh - Blue Fox",
            "software_id": sw_wz,
            "partner_id": p_bluefox,
            "storage_check_type": "docker_volume",
            "docker_container": "single-node-wazuh.indexer-1",
            "storage_check_path": "single-node_wazuh-indexer-data",
        })

    if sw_vw and p_pmeconforme:
        new_services.append({
            "name": "Vaultwarden - PME Conforme",
            "software_id": sw_vw,
            "partner_id": p_pmeconforme,
            "storage_check_type": "container_directory",
            "docker_container": "pme-conforme-vaultwarden",
            "storage_check_path": "/data",
        })

    if sw_n8n and p_pmeconforme:
        new_services.append({
            "name": "n8n - PME Conforme",
            "software_id": sw_n8n,
            "partner_id": p_pmeconforme,
            "storage_check_type": "postgres",
            "docker_container": "pme-conforme-n8n-db",
            "storage_check_db_name": "n8n",
            "storage_check_db_user": "n8n",
        })

    # Create services using ORM for proper sequence assignment
    Service = env["hosting.service"]
    created_count = 0

    for vals in new_services:
        # Check if already exists (by name)
        existing = Service.search([("name", "=", vals["name"])], limit=1)
        if existing:
            _logger.info("Service '%s' already exists (id=%d), skipping", vals["name"], existing.id)
            continue

        # Add defaults
        vals.setdefault("state", "active")
        vals.setdefault("environment", "production")
        vals.setdefault("server_id", server_id)
        vals.setdefault("user_id", user_id)

        try:
            service = Service.create(vals)
            created_count += 1
            _logger.info("Created service '%s' (%s)", service.name, service.code)
        except Exception as e:
            _logger.warning("Failed to create service '%s': %s", vals["name"], e)

    _logger.info("Created %d new hosting services", created_count)


def migrate(cr, version):
    _logger.info("Post-migrate: populating storage config on existing services")
    _populate_existing_storage_configs(cr)

    _logger.info("Post-migrate: creating new hosting services")
    env = api.Environment(cr, SUPERUSER_ID, {})
    _create_new_services(cr, env)
