class InvoiceNotFoundException(Exception):
    def __init__(self, id):
        super().__init__(f"No se encontró la factura de la cita con id {id}")
