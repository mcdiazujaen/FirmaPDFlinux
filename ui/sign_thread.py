from PySide6.QtCore import QThread, Signal
from core.autofirma import sign_pdf_multiple_zones

class SignThread(QThread):
    # Señal emitida al finalizar la operación: (success, message, text_overflow)
    finished_signal = Signal(bool, str, bool)

    def __init__(self, input_pdf, output_pdf, zones, cert_filter, sig_text, rubric_path,
                 autofirma_path, font_name, font_size, rubric_layout,
                 store="auto", store_pkcs12_path="", store_pkcs12_password=""):
        super().__init__()
        self.input_pdf = input_pdf
        self.output_pdf = output_pdf
        self.zones = zones
        self.cert_filter = cert_filter
        self.sig_text = sig_text
        self.rubric_path = rubric_path
        self.autofirma_path = autofirma_path
        self.font_name = font_name
        self.font_size = font_size
        self.rubric_layout = rubric_layout
        self.store = store
        self.store_pkcs12_path = store_pkcs12_path
        self.store_pkcs12_password = store_pkcs12_password

    def run(self):
        # Ejecutar firma múltiple secuencial
        success, message, text_overflow = sign_pdf_multiple_zones(
            input_pdf_path=self.input_pdf,
            output_pdf_path=self.output_pdf,
            zones=self.zones,
            cert_filter=self.cert_filter,
            signature_text=self.sig_text,
            rubric_path=self.rubric_path,
            autofirma_path=self.autofirma_path,
            font_name=self.font_name,
            font_size=self.font_size,
            rubric_layout=self.rubric_layout,
            store=self.store,
            store_pkcs12_path=self.store_pkcs12_path,
            store_pkcs12_password=self.store_pkcs12_password
        )
        self.finished_signal.emit(success, message, text_overflow)
