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


def execute_autofirma(autofirma_path, input_path, output_path, config_str, cert_filter=None):
    """Ejecuta una invocación simple de AutoFirma con la configuración dada."""
    if not autofirma_path:
        autofirma_path = detect_autofirma_path()
        
    # Construir el comando.
    # En macOS si es el .jar, se debe ejecutar con 'java -jar'
    cmd = []
    if autofirma_path.endswith(".jar"):
        cmd = ["java", "-jar", autofirma_path]
    else:
        cmd = [autofirma_path]
    cmd.extend(["sign", "-i", input_path, "-o", output_path, "-format", "pades"])
    
    # Agregar la configuración
    cmd.extend(["-config", config_str])
    
    # Agregar el filtro si se requiere firma silenciosa
    if cert_filter:
        cmd.extend(["-filter", f"subject.contains:{cert_filter}"])
        
    print(f"Ejecutando AutoFirma: {autofirma_path} sign -i {input_path} -o {output_path}")
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
                            font_name="Helvetica", font_size=0, rubric_layout="side_by_side"):
    """
    Orquesta la firma de un PDF para múltiples zonas con sello visual visible.
    
    Estrategia:
    1. Usar PyMuPDF para insertar el sello visual (imagen + texto) directamente en
       el PDF antes de firmarlo. Esto garantiza la visibilidad independientemente
       de las limitaciones del CLI de AutoFirma en Linux.
    2. Llamar a AutoFirma para que añada la firma criptográfica (PAdES) sobre el
       PDF ya sellado visualmente.
    
    Este enfoque produce un PDF con:
      - El sello gráfico visible en las coordenadas seleccionadas
      - La firma criptográfica válida y verificable
    """
    from core.pdf_handler import stamp_visual_signature

    if not zones:
        return False, "No se han definido zonas de firma."
        
    if not autofirma_path:
        autofirma_path = detect_autofirma_path()

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
            cert_filter=cert_filter
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
