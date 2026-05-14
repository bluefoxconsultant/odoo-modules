# Blue Fox — Loi 25 Suite

Bundle meta-module that pulls in the Blue Fox Quebec **Loi 25** (Act respecting the protection of personal information) compliance stack on a single install.

## Included modules

| Module | Role |
|---|---|
| [`audit_ti`](../audit_ti) | IT security audit management |
| [`privacy_consent`](../privacy_consent) | Consents, document destruction, anonymization |
| [`project_knowledge_matrix`](../project_knowledge_matrix) | Knowledge base for compliance policies and documentation |

Installing `bf_loi25_suite` installs all three. Uninstalling it does **not** uninstall them — Odoo only cascades `depends` in one direction.

## License

GNU LGPL-3. See [`../LICENSE`](../LICENSE) for the full text.
