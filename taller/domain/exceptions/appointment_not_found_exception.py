class AppointmentNotFoundException(Exception):
    def __init__(self, id):
        super().__init__(f"No se encontró cita con id {id}")
