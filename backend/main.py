"""
Punto de entrada para uvicorn: `uvicorn main:app`.

Toda la aplicación vive en el paquete `app/`. Este fichero solo la instancia.
"""
from app import create_app

app = create_app()
