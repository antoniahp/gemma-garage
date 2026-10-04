from taller.domain.client import Client
from taller.domain.repositories.client_repository import ClientRepository

from taller.application.find_clients.find_clients_query import FindClientsQuery


class FindClientsQueryHandler:
    def __init__(self, client_repository: ClientRepository):
        self.client_repository = client_repository

    def handle(self, query: FindClientsQuery) -> list[Client]:
        return self.client_repository.find_with_activity(query.text)
