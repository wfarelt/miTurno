from tenants.models import Business


class CurrentTenantMiddleware:
    """Attach the active business to the request object."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        tenant_slug = request.headers.get("X-Business-Slug")
        host = request.get_host().split(":")[0]
        host_parts = host.split(".")

        if not tenant_slug and len(host_parts) > 2:
            tenant_slug = host_parts[0]

        if tenant_slug:
            request.tenant = Business.objects.filter(
                slug=tenant_slug,
                is_active=True,
            ).first()

        return self.get_response(request)