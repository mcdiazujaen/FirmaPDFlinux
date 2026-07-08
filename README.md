# FirmaPDF - Aplicación de Firma de PDF

Aplicación de escritorio escrita en Python y PySide6 (Qt) que permite visualizar documentos PDF, definir de forma visual una o más zonas de firma y firmar digitalmente el documento invocando a la aplicación oficial **AutoFirma**.

## Características

* **Visor de PDF con Zoom:** Visualiza páginas completas con un renderizado nítido mediante PyMuPDF (`fitz`).
* **Selección Gráfica de Zonas:** Dibuja mediante arrastre de ratón (click y arrastrar) los rectángulos exactos en las páginas del PDF donde quieres que aparezca la firma.
* **Drag & Drop (Arrastrar y Soltar):** Suelta archivos PDF directamente en el visor central para abrirlos al instante.
* **Firma Única o Múltiple:** Soporte para firmar en múltiples páginas o múltiples zonas del mismo documento. La aplicación encadena secuencialmente llamadas a AutoFirma.
* **Modo Silencioso o Headless:** Configura un filtro de certificado (por ejemplo, parte de tu DNI/NIE o nombre) para realizar firmas instantáneas en segundo plano sin que aparezca continuamente el selector de certificados de AutoFirma.
* **Soporte de Almacenes de Claves (Key Stores):** Permite configurar en cada perfil el almacén a utilizar: automático, Windows, macOS, Mozilla/Firefox, o bien una ruta directa a un fichero PKCS12 (`.p12` o `.pfx`).
* **Cofirma Inteligente (Cosign):** Detección automática de firmas previas en el PDF para usar la instrucción `cosign` en lugar de `sign` de AutoFirma de manera totalmente transparente.
* **Visualización del Documento Firmado en Nueva Pestaña:** Al finalizar el proceso de firma con éxito, la aplicación abre automáticamente una pestaña secundaria ("Documento Firmado") para que puedas previsualizar e inspeccionar el documento resultante con las firmas estampadas, manteniendo la pestaña del original al lado.
* **Personalización de Firma:** Permite subir una imagen de rúbrica (firma manuscrita) y personalizar el texto descriptivo que acompaña al sello digital.
* **Tema Claro y Oscuro:** Interfaz intercambiable con estilos QSS premium.
* **Persistencia:** La ruta de AutoFirma, perfiles de firma, almacenes y preferencias se guardan de forma segura en la configuración.

## Requisitos e Instalación

Para ejecutar este proyecto necesitas tener instalado **Python 3.8+** y tener la aplicación **AutoFirma** instalada en tu equipo.

1. **Entorno Virtual (Recomendado):**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # En Linux/macOS
    # o bien: .venv\Scripts\activate  # En Windows
    ```

2. **Instalar dependencias:**

    ```bash
    pip install -r requirements.txt
    ```

## Cómo Ejecutar la Aplicación

Con el entorno virtual activado, ejecuta:

```bash
python main.py
```

## Integración con AutoFirma

La aplicación busca de forma automática el ejecutable de AutoFirma en las rutas típicas del sistema operativo:

* **Windows:** `C:\Program Files\AutoFirma\AutoFirma\AutoFirmaCommandLine.exe`
* **Linux:** `/usr/bin/autofirma` o `/usr/bin/AutoFirma`
* **macOS:** `/Applications/AutoFirma.app/Contents/Resources/JAR/AutoFirma.jar`

Si tu instalación se encuentra en una ruta personalizada, puedes examinar y asignarla directamente desde el panel de ajustes en la barra lateral.

### Almacén de Claves y Certificados (Keystores)

Puedes configurar el almacén de certificados que utilizará AutoFirma dentro de la ventana de **Configuración de Firma** de cada perfil:

* **Auto (por defecto):** Delega la búsqueda al comportamiento estándar de AutoFirma según el sistema operativo.
* **Windows:** Fuerza el uso del almacén de certificados del sistema operativo Windows.
* **Mac (Llavero del sistema):** Fuerza el uso del llavero (Keychain) en macOS (parámetro `-store mac`).
* **Mozilla / Firefox:** Utiliza el almacén de certificados propio del navegador Mozilla Firefox.
* **PKCS12 (.p12 / .pfx):** Permite usar un fichero de certificado local directamente seleccionando su ruta. Para este almacén, la aplicación solicitará la contraseña de forma interactiva y segura justo antes de realizar la firma, solicitándola una única vez por documento.

### Detección de Cofirma (Cosign)

La aplicación analiza automáticamente el fichero PDF antes de iniciar la firma:

1. Si el archivo **no está firmado**, se invoca el subcomando `sign` de AutoFirma para aplicar la primera firma.
2. Si el archivo **ya está firmado digitalmente**, la aplicación lo detecta de forma automática y cambia dinámicamente la instrucción a **`cosign`** (cofirmar). Esto asegura que no se alteren ni invaliden los metadatos de las firmas criptográficas previas.
*Nota:* El sello visual se inserta en el PDF mediante PyMuPDF de forma previa a la invocación de AutoFirma.

### Nota Importante para usuarios de Ubuntu 24 (Linux)

Para que la firma digital funcione correctamente en **Ubuntu 24**, el certificado digital debe estar instalado en el navegador **Google Chrome** (en caso de usar la opción por defecto/auto). AutoFirma utiliza el almacén de certificados de este navegador en sistemas Linux para localizar las firmas válidas.

**Pasos para instalar el certificado en Google Chrome:**

1. Abre **Google Chrome**.
2. Haz clic en los tres puntos verticales en la esquina superior derecha y selecciona **Configuración** (o ve a `chrome://settings` en la barra de direcciones).
3. En la barra lateral izquierda, haz clic en **Privacidad y seguridad**.
4. Selecciona **Seguridad**.
5. Desplázate hacia abajo y haz clic en **Gestionar certificados** (o **Gestionar certificados del dispositivo**).
6. Ve a la pestaña **Tus certificados** (o la sección equivalente de certificados de usuario).
7. Haz clic en **Importar**.
8. Busca y selecciona tu archivo de certificado digital (con extensión `.p12` o `.pfx`) e introduce la contraseña del certificado cuando se te solicite.
9. Reinicia la aplicación **FirmaPDF** y AutoFirma si las tenías abiertas para que los cambios surtan efecto.

## Generación del Ejecutable Empaquetado

Para empaquetar la aplicación en un archivo ejecutable independiente (de modo que se pueda distribuir y ejecutar en ordenadores que no tengan instalado Python), se utiliza **PyInstaller**.

1. **Instalar PyInstaller** en el entorno virtual:

   ```bash
   pip install pyinstaller
   ```

2. **Generar el ejecutable** usando el archivo de especificación preconfigurado (`FirmaPDF.spec`):

   ```bash
   pyinstaller FirmaPDF.spec
   ```

3. **Ubicar el ejecutable:**
   * El ejecutable resultante se guardará en la carpeta `dist/` (por ejemplo, `dist/FirmaPDF` en Linux/macOS o `dist/FirmaPDF.exe` en Windows).
   * Los archivos temporales generados durante la compilación se guardarán en la carpeta `build/` (esta carpeta se puede eliminar tras el proceso).
