"""drf-spectacular schema extensions.

Teaches the OpenAPI generator about Atlas's sole API auth — the ``X-API-Key`` header
(:class:`api.authentication.APIKeyAuthentication`) — so the generated schema and the
``/api/docs/`` page actually declare the security scheme. Without this, drf-spectacular
could not resolve the custom authenticator and warned on every single view, leaving the
documented contract (which the MCP server and other clients depend on) with no auth at all.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "api.authentication.APIKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }


class QueryKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """The `?key=` variant used only by the calendar feed (calendar apps send no headers)."""

    target_class = "api.authentication.QueryKeyAuthentication"
    name = "ApiKeyQuery"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "query", "name": "key"}
