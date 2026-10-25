# La Campana Crypto

Página premercado de bitcoin, cripto y el mercado americano. Incluye:
- cronómetro a la apertura;
- índice de miedo y codicia;
- futuros, tasas, megacaps y petróleo;
- agenda macro y alerta del día siguiente.

Los datos se actualizan solos y no tienes que escribir nada a mano.

## Cómo funciona

```
GitHub Actions (cada 15 min)          Cloudflare Pages (gratis)
  └─ corre scripts/actualizar_datos.py   └─ sirve public/index.html con tu dominio
       └─ guarda datos.json en la rama "datos"
                                          El navegador del visitante:
                                            • lee datos.json desde GitHub cada 5 min
                                            • pide precios cripto en vivo a CoinGecko cada minuto
```

- **Precios cripto, dominancia y capitalización:** CoinGecko. El precio de BTC, ETH y SOL se actualiza en vivo en la página.
- **Miedo y codicia:** alternative.me.
- **Niveles de BTC:** VWAP del día, apertura diaria y apertura semanal, calculados con velas de 5 minutos de Coinbase.
- **Futuros, índices, bonos, dólar, VIX, petróleo y megacaps con premercado:** Yahoo Finance, a través de la librería `yfinance`.
- **Niveles del NQ:** sesión previa (9:30–16:00 ET) y rango overnight.
- **Agenda macro y alerta de mañana:** calendario de Forex Factory, solo EE. UU., impacto alto y medio.
- **Feriados y cierres anticipados de NYSE:** se calculan solos cada año.

Si una fuente falla, el resto se sigue mostrando y esa sección dice "Sin datos por ahora". Si la página no puede leer `datos.json`, muestra datos de muestra marcados como tales.

---

## Paso 1 · Subir el proyecto a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no tienes.
2. Arriba a la derecha toca **+ → New repository**:
   - nombre: `la-campana-crypto`;
   - visibilidad: **Public**, necesaria para que la página pueda leer los datos;
   - toca **Create repository**.
3. En el repositorio vacío toca **uploading an existing file**. Arrastra **todo el contenido** de esta carpeta:
   - `public/`
   - `scripts/`
   - `.github/`
   - `requirements.txt`
   - `README.md`
   - `.gitignore`

   Luego toca **Commit changes**.

   > En Mac, la carpeta `.github` está oculta. Pulsa `Cmd + Shift + .` en el Finder para verla. Si no se sube, crea el archivo a mano: **Add file → Create new file**, escribe `.github/workflows/actualizar-datos.yml` como nombre y pega su contenido.

## Paso 2 · Poner tu usuario y tu correo

1. Abre `public/index.html` en GitHub y toca el lápiz para editarlo.
2. Busca esta línea cerca del inicio del `<script>` y cambia `TU_USUARIO` por tu usuario de GitHub:
   ```js
   DATOS_URL: "https://raw.githubusercontent.com/TU_USUARIO/la-campana-crypto/datos/datos.json",
   ```
3. Abre `public/privacidad.html` y cambia `tu-correo@ejemplo.com` por tu correo de contacto.
4. Guarda con **Commit changes**.

## Paso 3 · Activar la actualización automática

1. En el repositorio, ve a la pestaña **Actions**. Si pide permiso, toca **I understand my workflows, go ahead and enable them**.
2. Elige **Actualizar datos** a la izquierda, toca **Run workflow → Run workflow** y espera 1–2 minutos.
3. Comprueba que funcionó:
   - debe aparecer una rama llamada **datos**;
   - abre en el navegador `https://raw.githubusercontent.com/TU_USUARIO/la-campana-crypto/datos/datos.json` y deberías ver los números.
4. Si falla con un error de permisos, ve a **Settings → Actions → General → Workflow permissions**, marca **Read and write permissions** y guarda.

A partir de ahí se ejecuta solo:
- cada 15 minutos en días de semana, desde la madrugada hasta pasado el cierre de Nueva York (de 08:00 a 22:45 UTC);
- cada hora el resto del tiempo.

## Paso 4 · Publicar la página en Cloudflare Pages

1. Crea una cuenta gratis en [cloudflare.com](https://dash.cloudflare.com/sign-up).
2. Ve a **Workers y Pages → Crear → Pages → Conectar a Git**.
3. Autoriza GitHub y elige `la-campana-crypto`.
4. Configura así:
   - **Rama de producción:** `main`
   - **Framework:** Ninguno
   - **Comando de compilación:** déjalo vacío
   - **Directorio de salida:** `public`
5. Toca **Guardar e implementar**. En un minuto tendrás la página en `la-campana-crypto.pages.dev`.
6. **Importante:** ve a **Configuración → Compilaciones → Ramas** y desactiva las implementaciones de vista previa. Elige "Ninguna", o incluye solo `main`. Si no lo haces, cada actualización de la rama `datos` gastará una compilación, y el plan gratis tiene 500 al mes.

## Paso 5 · Comprar y conectar tu dominio

1. En Cloudflare, ve a **Registro de dominios → Registrar dominio** y busca el nombre, por ejemplo `lacampanacrypto.com`. Cloudflare cobra el precio del registro, sin recargo.
2. Una vez comprado, entra a tu proyecto de Pages y ve a **Dominios personalizados → Configurar un dominio**. Escribe el dominio y confirma. Cloudflare configura el DNS y el certificado HTTPS solo.

## Paso 6 · Google AdSense (cuando tengas algo de tráfico)

1. Solicita la cuenta en [adsense.google.com](https://adsense.google.com) con tu dominio.
2. AdSense te da un código `<script ...>`. Pégalo en `public/index.html`, donde dice `<!-- Google AdSense ... -->`.
3. Crea el archivo `public/ads.txt` con la línea exacta que te indique AdSense. Tiene esta forma:
   ```
   google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0
   ```
4. Cuando te aprueben, reemplaza los recuadros `<div class="ad ...">` por los bloques de anuncio que crees en AdSense. También puedes activar **Anuncios automáticos** y borrar esos recuadros.

La página de privacidad ya menciona las cookies de AdSense, y el pie de página enlaza a ella.

---

## Mantenimiento

- **GitHub pausa las tareas programadas** de un repositorio público si pasan 60 días sin actividad. Te llegará un correo. Para reactivarla, ve a **Actions → Actualizar datos → Enable workflow**. Hacer un cambio pequeño en el repositorio de vez en cuando lo evita.
- **Ver si algo falló:** en **Actions** cada ejecución aparece en verde o en rojo. Dentro se ve qué fuente falló, con líneas `[aviso] ... falló`.
- **Probar el script en tu computadora:**
  ```bash
  pip install -r requirements.txt
  python scripts/actualizar_datos.py salida/datos.json
  ```

## Antes de crecer: uso comercial de los datos

- **CoinGecko** y **alternative.me** permiten uso gratuito citando la fuente. Ya está en el pie de página.
- **Yahoo Finance** (`yfinance`) y el calendario de **Forex Factory** son fuentes no oficiales, pensadas para uso personal. Para un sitio con anuncios funcionan, pero si el sitio crece conviene cambiarlos por un proveedor de datos con licencia comercial, por ejemplo Twelve Data, Financial Modeling Prep o Polygon. Solo habría que modificar las funciones `cotizacion()` y `calendario()` del script.
- El aviso de que **no es asesoría financiera** debe quedarse siempre visible.
