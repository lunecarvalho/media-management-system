from django.core.paginator import Paginator


def paginar(request, queryset, size=20):
    return Paginator(queryset, size).get_page(request.GET.get('page'))
