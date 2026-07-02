import os
import sys
import subprocess
import shutil
import base64
import tempfile
from PySide6.QtGui import QImage
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt

def detect_autofirma_path():
    """Detecta la ruta por defecto de AutoFirma según el sistema operativo."""
    if sys.platform.startswith("win"):
        # Rutas comunes en Windows
        paths = [
            r"C:\Program Files\AutoFirma\AutoFirma\AutoFirmaCommandLine.exe",
            r"C:\Program Files (x86)\AutoFirma\AutoFirma\AutoFirmaCommandLine.exe"
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return "AutoFirmaCommandLine.exe"  # Asumir que podría estar en el PATH
    elif sys.platform.startswith("darwin"):
        # En macOS puede estar el Jar o el wrapper
        path = "/Applications/AutoFirma.app/Contents/Resources/JAR/AutoFirma.jar"
        if os.path.exists(path):
            return path
        return "AutoFirma"
    else:
        # Linux
        paths = [
            "/usr/bin/autofirma",
            "/usr/bin/AutoFirma",
            "/usr/lib/AutoFirma/AutoFirma.jar"
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return "autofirma"


def is_pdf_signed(pdf_path):
    """
    Detecta si un PDF ya contiene al menos una firma digital (campo de firma AcroForm).
    Devuelve True si se encuentra al menos un widget de tipo firma, False en caso contrario.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                for widget in page.widgets():
                    if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                        return True
        finally:
            doc.close()
        return False
    except Exception as e:
        print(f"[is_pdf_signed] Error al detectar firma: {e}")
        return False


def execute_autofirma(autofirma_path, input_path, output_path, config_str, cert_filter=None,
                      store="auto", store_pkcs12_password="", use_cosign=False):
    """
    Ejecuta una invocación de AutoFirma con la configuración dada.
    
    Parámetros:
      store               -- almacén de claves: "auto"|"windows"|"mac"|"mozilla"|"pkcs12"
      store_pkcs12_password -- contraseña del fichero .p12 (solo cuando store=="pkcs12")
      use_cosign          -- True para usar el subcomando 'cosign' en lugar de 'sign'
    """
    if not autofirma_path:
        autofirma_path = detect_autofirma_path()

    # Construir el comando.
    # En macOS si es el .jar, se debe ejecutar con 'java -jar'
    cmd = []
    if autofirma_path.endswith(".jar"):
        cmd = ["java", "-jar", autofirma_path]
    else:
        cmd = [autofirma_path]

    # Elegir subcomando según si el documento ya está firmado
    subcmd = "cosign" if use_cosign else "sign"
    cmd.extend([subcmd, "-i", input_path, "-o", output_path, "-format", "pades"])

    # Agregar almacén de claves si no es automático
    if store and store != "auto":
        if store == "pkcs12":
            # store_pkcs12_path se construye en sign_pdf_multiple_zones y se pasa como store
            # En este punto store ya viene como "pkcs12:<ruta>"
            cmd.extend(["-store", store])
        else:
            cmd.extend(["-store", store])
        # Contraseña del PKCS12 (solo aplica cuando el store empieza por 'pkcs12:')
        if store.startswith("pkcs12:") and store_pkcs12_password:
            cmd.extend(["-password", store_pkcs12_password])

    # Agregar la configuración
    cmd.extend(["-config", config_str])

    # Agregar el filtro si se requiere firma silenciosa
    if cert_filter:
        cmd.extend(["-filter", f"subject.contains:{cert_filter}"])

    print(f"Ejecutando AutoFirma: {autofirma_path} {subcmd} -i {input_path} -o {output_path}")
    print(f"Config:\n{config_str}")
    
    try:
        # Ejecutar el comando. Capturamos salida estándar y errores.
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode == 0:
            return True, "Firma realizada con éxito."
        else:
            error_msg = ""
            if result.stdout and result.stdout.strip():
                error_msg += f"Salida: {result.stdout.strip()}\n"
            if result.stderr and result.stderr.strip():
                error_msg += f"Detalles: {result.stderr.strip()}"
            if not error_msg:
                error_msg = "Error desconocido sin salida en consola."
            return False, f"AutoFirma devolvió error (código {result.returncode}):\n{error_msg}"
    except Exception as e:
        return False, f"No se pudo ejecutar AutoFirma: {str(e)}"


def sign_pdf_multiple_zones(input_pdf_path, output_pdf_path, zones, cert_filter=None,
                            signature_text=None, rubric_path=None, autofirma_path=None,
                            font_name="Helvetica", font_size=0, rubric_layout="side_by_side",
                            store="auto", store_pkcs12_path="", store_pkcs12_password=""):
    """
    Orquesta la firma de un PDF para múltiples zonas con sello visual visible.

    Estrategia:
    1. Usar PyMuPDF para insertar el sello visual (imagen + texto) directamente en
       el PDF antes de firmarlo. Esto garantiza la visibilidad independientemente
       de las limitaciones del CLI de AutoFirma en Linux.
    2. Detectar automáticamente si el PDF de entrada ya contiene firmas digitales.
       - Si ya está firmado → usar 'cosign' (cofirma al mismo nivel).
       - Si no está firmado → usar 'sign' (primera firma).
    3. Llamar a AutoFirma para que añada la firma criptográfica (PAdES) sobre el
       PDF ya sellado visualmente.

    Este enfoque produce un PDF con:
      - El sello gráfico visible en las coordenadas seleccionadas
      - La firma criptográfica válida y verificable

    Parámetros adicionales:
      store               -- almacén de claves: "auto"|"windows"|"mac"|"mozilla"|"pkcs12"
      store_pkcs12_path   -- ruta al fichero .p12/.pfx (cuando store=="pkcs12")
      store_pkcs12_password -- contraseña del fichero .p12 (cuando store=="pkcs12")
    """
    from core.pdf_handler import stamp_visual_signature

    if not zones:
        return False, "No se han definido zonas de firma."

    if not autofirma_path:
        autofirma_path = detect_autofirma_path()

    # ---------------------------------------------------------------
    # Detectar si el PDF de entrada ya está firmado digitalmente
    # ---------------------------------------------------------------
    already_signed = is_pdf_signed(input_pdf_path)
    if already_signed:
        print(f"[autofirma] PDF ya firmado detectado → se usará 'cosign' (cofirma)")
    else:
        print(f"[autofirma] PDF sin firmas previas detectado → se usará 'sign'")

    # ---------------------------------------------------------------
    # Construir el valor del parámetro -store para AutoFirma
    # ---------------------------------------------------------------
    effective_store = "auto"
    if store and store != "auto":
        if store == "pkcs12":
            if store_pkcs12_path:
                effective_store = f"pkcs12:{store_pkcs12_path}"
            else:
                print("[autofirma] ADVERTENCIA: store=pkcs12 pero no se ha especificado ruta al .p12")
        else:
            effective_store = store  # "windows", "mac", "mozilla"

    current_input = input_pdf_path
    temp_files = []

    try:
        # ---------------------------------------------------------------
        # PASO 1: Insertar todos los sellos visuales con PyMuPDF
        # ---------------------------------------------------------------
        fd, stamped_path = tempfile.mkstemp(suffix="_stamped.pdf")
        os.close(fd)
        temp_files.append(stamped_path)

        print(f"[stamp] Insertando {len(zones)} sello(s) visual(es) en: {stamped_path}")

        ok, msg, text_overflow = stamp_visual_signature(
            input_pdf_path=current_input,
            output_pdf_path=stamped_path,
            zones=zones,
            signature_text=signature_text,
            rubric_image_path=rubric_path,
            signer_name=cert_filter if cert_filter else None,
            font_name=font_name,
            font_size=font_size,
            rubric_layout=rubric_layout
        )

        if not ok:
            return False, f"Error al insertar sello visual: {msg}"

        current_input = stamped_path

        # ---------------------------------------------------------------
        # PASO 2: Firmar digitalmente con AutoFirma (una sola vez)
        # La firma criptográfica cubre el documento completo con todos los sellos
        # ---------------------------------------------------------------
        # Configuración mínima para firma PAdES silenciosa
        config_lines = ["headless=true"] if cert_filter else ["headless=false"]
        config_str = "\n".join(config_lines)

        print(f"[autofirma] Firmando digitalmente el documento sellado...")

        success, msg = execute_autofirma(
            autofirma_path=autofirma_path,
            input_path=current_input,
            output_path=output_pdf_path,
            config_str=config_str,
            cert_filter=cert_filter,
            store=effective_store,
            store_pkcs12_password=store_pkcs12_password,
            use_cosign=already_signed
        )

        if not success:
            return False, f"Fallo en la firma digital: {msg}", False

        return True, "Documento firmado correctamente con sello visible.", text_overflow
        
    finally:
        # Limpieza de archivos temporales
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                print(f"Error limpiando temporal {temp_path}: {e}")
