class ClientNotFoundException(Exception):
    def __init__(self, id):
        super().__init__(f"No se encontró cliente con id {id}")
