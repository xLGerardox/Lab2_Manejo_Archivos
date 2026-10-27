# Agenda de Contactos con Acceso Aleatorio

Laboratorio2 - Manejo de archivos

Aplicación de escritorio que guarda contactos en un archivo de registros de tamaño fijo, 
accede a ellos con seek() / tell()...

## Requisitos
- pip install fpdf2

## Estructura del registro (100 bytes)

| Campo | Largo | Posición (bytes) |
|---|---|---|
| id | 6 | 0 - 5 |
| nombre | 30 | 6 - 35 |
| teléfono | 15 | 36 - 50 |
| correo | 30 | 51 - 80 |
| ciudad | 18 | 81 - 98 |
| fin de línea (\n) | 1 | 99 |
| **Total** | **100** | |



## Uso

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fpdf2
python3 app.py
```

Los datos se guardan en la carpeta `datos/`: `contactos.dat` (registros de 100 bytes),
`indice.json` (índice id -> registro), `contactos.sha256`,
`exportaciones/` (JSON y PDF) y `respaldos/` (ZIP).

Pruebas automáticas: `python3 -m unittest discover -s tests`