"""Modal-first forms (Owner idea #18).

Form views render inside a shared modal for HTMX requests and stay full pages
for direct navigation — one view, both behaviors, no duplicated forms.
"""

from django.http import HttpResponse


class ModalFormMixin:
    """Mix into Create/Update views ahead of the generic view classes."""

    modal_title = ""

    def _is_htmx(self) -> bool:
        return self.request.headers.get("HX-Request") == "true"

    def get_template_names(self):
        if self._is_htmx():
            return ["_modal_form.html"]
        return super().get_template_names()

    def get_modal_title(self) -> str:
        if self.modal_title:
            return self.modal_title
        name = self.model._meta.verbose_name
        return f"Edit {name}" if getattr(self, "object", None) else f"Add {name}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["modal_title"] = self.get_modal_title()
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self._is_htmx():
            # 204 keeps HTMX from swapping; HX-Redirect reloads onto the success URL
            return HttpResponse(status=204, headers={"HX-Redirect": response.url})
        return response
