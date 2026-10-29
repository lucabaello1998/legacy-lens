"""legacy-lens: radiografia de un sistema legacy PHP/MySQL.

El objetivo es responder, en un solo comando, tres preguntas que aparecen
siempre antes de una migracion:

1. Que tan raro es el esquema (sin claves, sin foreign keys, tipos raros).
2. Que tan riesgoso es el codigo (SQL concatenado, funciones extintas, secretos).
3. Cuanto duele migrarlo, con un numero y un plan de accion.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
