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
