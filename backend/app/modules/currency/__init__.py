"""Currency module.

Cross-cutting (igual que `auth/`, `ai/`): cualquier módulo de dominio
puede importar `currency.service` para convertir importes entre
monedas. EUR es la base canónica de las tasas almacenadas; las
conversiones X→Y se componen vía EUR.
"""
