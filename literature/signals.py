"""Keep `ReferenceText` in step with the PDF on every reference save (slice 8)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Reference


@receiver(post_save, sender=Reference)
def index_pdf_text(sender, instance: Reference, **kwargs):
    from .fulltext import needs_extraction
    from .tasks import extract_text_task

    if instance.pdf and needs_extraction(instance):
        extract_text_task(instance.pk)
    elif not instance.pdf:
        from .models import ReferenceText

        ReferenceText.objects.filter(reference=instance).delete()


@receiver(post_save, sender=Reference)
def link_citing_works(sender, instance: Reference, created=False, update_fields=None, **kwargs):
    """#530: a paper that joins the library (or gains a DOI / OpenAlex id) stops being a
    "new citation" alert — the citing work that is this paper gets linked to it. A save that
    names other fields (a reading position, a watch stamp) cannot change identity: no query."""
    if update_fields is not None and not created:
        if not set(update_fields) & {"doi", "openalex_id"}:
            return
    if instance.doi or instance.openalex_id:
        from .citing import link_reference

        link_reference(instance)


@receiver(post_save, sender=Reference)
def link_feed_items(sender, instance: Reference, created=False, update_fields=None, **kwargs):
    """#531: a paper that joins the library (or gains a DOI / arXiv id) stops being a feed
    entry to add — the entries that are this paper get linked to it. Saves naming other fields
    cannot change identity: no query."""
    if update_fields is not None and not created:
        if not set(update_fields) & {"doi", "arxiv_id"}:
            return
    if instance.doi or instance.arxiv_id:
        from .feeds import link_reference

        link_reference(instance)
