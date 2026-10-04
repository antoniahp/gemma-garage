from django.db.models import Count, Q

from taller.domain.client import Client
from taller.domain.repositories.client_criteria import ClientCriteria
from taller.domain.repositories.client_repository import ClientRepository


class DbClientRepository(ClientRepository):
    def save(self, client: Client) -> None:
        client.save()

    def find_by_criteria(self, criteria: ClientCriteria) -> list[Client]:
        queryset = Client.objects.all()
        if criteria.id is not None:
            queryset = queryset.filter(id=criteria.id)
        if criteria.name_iexact is not None:
            queryset = queryset.filter(name__iexact=criteria.name_iexact)
        if criteria.link_token is not None:
            queryset = queryset.filter(link_token=criteria.link_token)
        return list(queryset)

    def find_with_activity(self, text: str) -> list[Client]:
        queryset = Client.objects.annotate(
            visits=Count("appointments"),
            waiting=Count("reminder", filter=Q(reminder__sent=False)),
        )
        if text:
            queryset = queryset.filter(Q(name__icontains=text) | Q(phone__icontains=text))
        return list(queryset)

    def find_names(self) -> list[str]:
        return list(Client.objects.values_list("name", flat=True))
