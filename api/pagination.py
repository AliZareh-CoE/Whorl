"""Page-number pagination that honours `?page_size=` (#571).

DRF's stock `PageNumberPagination` ships with `page_size_query_param = None`, so every
`?page_size=200` the SPA sent was silently ignored and every list came back capped at the
default 50 — the Report page asked for 500 references and got 50, the Today page asked for
200 items and got 50. The cap is now real: up to `max_page_size` rows a page, the default
unchanged.
"""

from rest_framework.pagination import PageNumberPagination


class AtlasPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 500  # the largest a page in the SPA asks for (the Report's references)
