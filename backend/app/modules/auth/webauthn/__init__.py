"""Submódulo WebAuthn / Passkeys del módulo auth.

Permite que los usuarios registren credenciales asociadas a su dispositivo
(Touch ID, Windows Hello, llaves físicas, claves Apple/Google) y se
autentiquen sin password. Toda la criptografía vive en el dispositivo del
usuario; el backend solo guarda claves públicas y verifica firmas.
"""
