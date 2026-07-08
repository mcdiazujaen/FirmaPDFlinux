import fitz  # PyMuPDF
import os
import re
from datetime import datetime
from PySide6.QtGui import QImage
import logging

logger = logging.getLogger(__name__)

def validate_pdf_file(filepath: str) -> None:
    """Lanza ValueError si el fichero no es un PDF válido."""
    with open(filepath, "rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        raise ValueError(f"El fichero no es un PDF válido: {filepath!r}")

class PdfHandler:
    def __init__(self, filepath):
        validate_pdf_file(filepath)
        self.filepath = filepath
        self.doc = fitz.open(filepath)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def get_page_count(self):
        return len(self.doc)

    def get_page_size(self, page_num):
        """Devuelve el ancho y alto de la página en puntos (points)."""
        page = self.doc[page_num]
        rect = page.rect
        return rect.width, rect.height

    def render_page(self, page_num, scale=3.0):
        """Renderiza la página del PDF a alta resolución fija (ej. 3.0x = 216 DPI)."""
        page = self.doc[page_num]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convertir a QImage y hacer una COPIA profunda (.copy())
        # para evitar corrupción de memoria al destruirse la variable 'pix'.
        qimg = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            QImage.Format_RGB888
        ).copy()
        return qimg, pix.width, pix.height

    def close(self):
        self.doc.close()


# Mapa de fuentes soportadas por PyMuPDF (nombre legible → nombre interno)
SUPPORTED_FONTS = {
    "Helvetica":        "helv",
    "Helvetica Bold":   "hebo",
    "Times Roman":      "tiro",
    "Times Bold":       "tibo",
    "Courier":          "cour",
    "Courier Bold":     "cobo",
}


def qt_to_pdf_coords(qt_x, qt_y, qt_w, qt_h, zoom, pdf_h, pdf_w):
    """
    Convierte coordenadas de Qt (origen superior izquierdo, en píxeles con zoom)
    al sistema de coordenadas de PDF/AutoFirma (origen inferior izquierdo, en puntos).
    """
    # Escalar de píxeles a puntos (dividir por zoom)
    x_pt = qt_x / zoom
    y_pt = qt_y / zoom
    w_pt = qt_w / zoom
    h_pt = qt_h / zoom

    # Límites superiores en puntos
    x1 = max(0.0, min(x_pt, pdf_w))
    x2 = max(0.0, min(x_pt + w_pt, pdf_w))
    
    # Invertir Y (Qt superior izquierdo -> PDF inferior izquierdo)
    # y_pt + h_pt es la base del rectángulo en sistema superior izquierdo
    # pdf_h - (y_pt + h_pt) es la distancia desde la parte inferior de la página
    y1 = max(0.0, min(pdf_h - (y_pt + h_pt), pdf_h))
    y2 = max(0.0, min(pdf_h - y_pt, pdf_h))

    return {
        "lowerLeftX": round(x1),
        "lowerLeftY": round(y1),
        "upperRightX": round(x2),
        "upperRightY": round(y2)
    }


def _resolve_font_name(font_display_name):
    """Resuelve el nombre interno de PyMuPDF a partir del nombre legible."""
    return SUPPORTED_FONTS.get(font_display_name, "helv")


def stamp_visual_signature(input_pdf_path, output_pdf_path, zones,
                            signature_text=None, rubric_image_path=None,
                            signer_name=None, font_name="Helvetica",
                            font_size=0, rubric_layout="side_by_side"):
    """
    Inserta sellos de firma visibles en el PDF usando PyMuPDF directamente,
    sin depender de AutoFirma para la parte visual.
    
    Cada zona es un dict con:
      - 'page': número de página (0-based)
      - 'coords': dict con lowerLeftX, lowerLeftY, upperRightX, upperRightY (en puntos PDF)
    
    Parámetros adicionales:
      - font_name: nombre legible de fuente (ej. "Helvetica", "Times Roman").
      - font_size: tamaño de fuente en puntos (0 = cálculo automático).
      - rubric_layout:
          "side_by_side" → imagen en el tercio izquierdo, texto en los 2/3 derechos.
          "background"   → imagen de fondo ocupando toda el área; texto superpuesto
                           centrado horizontalmente y alineado en la parte superior.

    Devuelve: (ok: bool, message: str, text_overflow: bool)
    """
    doc = fitz.open(input_pdf_path)
    internal_font = _resolve_font_name(font_name)
    text_overflow = False
    
    try:
        for zone in zones:
            page_num = zone['page']
            coords = zone['coords']
            
            if page_num >= len(doc):
                continue
            
            page = doc[page_num]
            
            # Convertir coordenadas PDF (origen inferior izquierdo) a fitz.Rect (origen superior izquierdo)
            page_height = page.rect.height
            
            ll_x = coords['lowerLeftX']
            ll_y = coords['lowerLeftY']
            ur_x = coords['upperRightX']
            ur_y = coords['upperRightY']
            
            # fitz.Rect = (x0, y0, x1, y1) donde y0 < y1 y el origen es la esquina sup-izq
            rect_x0 = ll_x
            rect_y0 = page_height - ur_y   # convertir: superior izquierdo fitz
            rect_x1 = ur_x
            rect_y1 = page_height - ll_y   # convertir: inferior derecho fitz
            
            rect = fitz.Rect(rect_x0, rect_y0, rect_x1, rect_y1)
            
            # Decidir si hay imagen
            has_image = rubric_image_path and os.path.exists(rubric_image_path)
            
            rect_w = rect_x1 - rect_x0
            rect_h = rect_y1 - rect_y0
            margin = 4

            # Calcular tamaño de fuente
            if font_size and font_size > 0:
                effective_fontsize = float(font_size)
            else:
                # Automático: proporcional a la altura del área
                effective_fontsize = min(9.0, max(5.0, rect_h / 4.5))

            # ------------------------------------------------------------------
            # MODO: "background" – imagen de fondo, texto superpuesto arriba
            # ------------------------------------------------------------------
            if rubric_layout == "background" and has_image:
                # Insertar imagen ocupando toda el área
                img_rect = fitz.Rect(
                    rect_x0 + margin,
                    rect_y0 + margin,
                    rect_x1 - margin,
                    rect_y1 - margin
                )
                try:
                    page.insert_image(img_rect, filename=rubric_image_path, keep_proportion=True)
                except Exception as e:
                    logger.warning(f"[stamp] No se pudo insertar la imagen de rúbrica (fondo): {e}")
                    has_image = False

                # Texto superpuesto: ocupa todo el ancho, alineado arriba
                if signature_text:
                    text_rect = fitz.Rect(
                        rect_x0 + margin,
                        rect_y0 + margin,
                        rect_x1 - margin,
                        rect_y1 - margin
                    )
                    display_text = _prepare_display_text(signature_text, signer_name)
                    overflow = _insert_text(
                        page, text_rect, display_text,
                        internal_font, effective_fontsize,
                        align=fitz.TEXT_ALIGN_CENTER
                    )
                    if overflow:
                        text_overflow = True

            # ------------------------------------------------------------------
            # MODO: "side_by_side" – imagen izquierda (1/3), texto derecha (2/3)
            # ------------------------------------------------------------------
            else:
                if has_image:
                    # La imagen ocupa el tercio izquierdo del rectángulo
                    img_w = rect_w * 0.40
                    img_rect = fitz.Rect(
                        rect_x0 + margin,
                        rect_y0 + margin,
                        rect_x0 + img_w - margin,
                        rect_y1 - margin
                    )
                    try:
                        page.insert_image(img_rect, filename=rubric_image_path, keep_proportion=True)
                    except Exception as e:
                        logger.warning(f"[stamp] No se pudo insertar la imagen de rúbrica: {e}")
                        has_image = False

                if signature_text:
                    if has_image:
                        img_w = rect_w * 0.40
                        text_x0 = rect_x0 + img_w
                    else:
                        text_x0 = rect_x0 + margin

                    text_rect = fitz.Rect(
                        text_x0 + margin,
                        rect_y0 + margin,
                        rect_x1 - margin,
                        rect_y1 - margin
                    )
                    display_text = _prepare_display_text(signature_text, signer_name)
                    overflow = _insert_text(
                        page, text_rect, display_text,
                        internal_font, effective_fontsize,
                        align=fitz.TEXT_ALIGN_LEFT
                    )
                    if overflow:
                        text_overflow = True
        
        doc.save(output_pdf_path, garbage=4, deflate=True)
        return True, "Sello visual insertado correctamente.", text_overflow
    
    except Exception as e:
        return False, f"Error al insertar sello visual: {str(e)}", False
    
    finally:
        doc.close()


def _prepare_display_text(signature_text, signer_name):
    """Sustituye los marcadores dinámicos del texto de firma."""
    subject_name = signer_name if signer_name else "Firmante"
    display_text = signature_text.replace("$$SUBJECTCN$$", subject_name)

    def replace_signdate(match):
        java_fmt = match.group(1).strip()
        py_fmt = (
            java_fmt
            .replace("yyyy", "%Y")
            .replace("yy", "%y")
            .replace("dd", "%d")
            .replace("MM", "%m")
            .replace("HH", "%H")
            .replace("mm", "%M")
            .replace("ss", "%S")
        )
        return datetime.now().strftime(py_fmt)

    display_text = re.sub(
        r'\$\$SIGNDATE=([^$\n]+?)(?:\$\$|$)',
        replace_signdate,
        display_text
    )
    return display_text


def _insert_text(page, text_rect, text, fontname, fontsize, align):
    """
    Inserta texto en el rectángulo dado. Devuelve True si el texto desborda el área.
    Intenta reducir el tamaño de fuente antes de reportar desbordamiento.
    """
    import fitz
    
    # Crear un documento temporal en memoria para medir el texto sin manchar la página original
    tmp_doc = fitz.open()
    tmp_page = tmp_doc.new_page(width=text_rect.width, height=text_rect.height)
    measure_rect = fitz.Rect(0, 0, text_rect.width, text_rect.height)

    # Intentar con el tamaño especificado primero
    result = tmp_page.insert_textbox(
        measure_rect, text, fontsize=fontsize, fontname=fontname, align=align
    )
    
    if result >= 0:
        # Cabe perfectamente
        page.insert_textbox(
            text_rect, text, fontsize=fontsize, fontname=fontname,
            color=(0.1, 0.1, 0.4), align=align
        )
        tmp_doc.close()
        return False

    # Intentar reducir el tamaño de fuente automáticamente hasta un mínimo
    min_size = 5.0
    reduced = fontsize
    best_size = min_size
    
    while reduced > min_size:
        reduced = max(min_size, reduced - 0.5)
        r = tmp_page.insert_textbox(
            measure_rect, text, fontsize=reduced, fontname=fontname, align=align
        )
        if r >= 0:
            best_size = reduced
            break

    tmp_doc.close()
    
    # Insertar de verdad en la página original con el tamaño calculado
    page.insert_textbox(
        text_rect, text, fontsize=best_size, fontname=fontname,
        color=(0.1, 0.1, 0.4), align=align
    )
    return best_size == min_size and result < 0
