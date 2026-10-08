# Tablero de electricidad del Ecuador

Página en español sobre el embalse Mazar, la probabilidad de cortes y la generación del día. Se publica cifrada en GitHub Pages y se recalcula sola cada hora.

Dirección prevista: <https://screspo111-sys.github.io/Energ-a_SC/>

La página no se puede leer sin la contraseña. El cifrado es en el navegador (StatiCrypt, AES-256). Los CSV no se suben a Pages: van dentro del HTML cifrado.

El repositorio es público. Quien entre a GitHub ve los scripts y la historia en CSV. Lo que queda reservado al dueño es la página publicada. La contraseña no está en el repositorio: vive en el secreto `DASHBOARD_PASSWORD`.

## Qué hay que hacer una vez

1. Crear el secreto `DASHBOARD_PASSWORD` en <https://github.com/screspo111-sys/Energ-a_SC/settings/secrets/actions/new> (el nombre va exactamente así).
2. En Settings → Pages, el origen tiene que ser **GitHub Actions**. Si este repositorio no pudo activarlo, actívelo ahí.
3. Abrir la pestaña Actions, elegir **Tablero de electricidad** y pulsar **Run workflow**.

Si el secreto no existe, el paso de cifrado falla y no se publica una página legible. No hay contraseña de respaldo.

## Cada hora

El flujo `.github/workflows/tablero.yml` (nombre: **Tablero de electricidad**):

1. Comprueba si responden CELEC SUR (puerto 8443), CENACE y ARCONEL.
2. Actualiza los datos. Si una fuente no responde, conserva la anterior y la página dice de qué fecha es.
3. Recalcula días hasta 2.115 m, escenarios y probabilidad.
4. Cifra `site/index.html` y lo publica en Pages.
5. Guarda un commit de historia solo cuando cambian las cifras, no en cada hora.

Para correrlo en local, sin publicar:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash dashboard/scripts/actualizar_tablero_energia.sh
```

`--sin-red` recalcula con los CSV ya guardados y no llama a las fuentes.
