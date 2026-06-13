"""Mirror ManuscriptFile writes into the unified Document tree (epic #30, slice 1c-ii-B2).

Every create/edit/rename/delete of a ManuscriptFile re-syncs its manuscript's tree
mirror, so the file workspace stays live without the editor/compile/API changing their
source of truth. The sync writes Documents (never ManuscriptFiles), so there is no
recursion. Manuscript-source nodes are scoped out of the general Documents UI (B1).
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


def _resync(manuscript):
    from documents.models import Document, Folder

    from .tree_sync import resync_manuscript_tree

    root, main_node = resync_manuscript_tree(manuscript, Folder=Folder, Document=Document)
    # keep the FKs current without retriggering Manuscript.save's alias sync
    type(manuscript).objects.filter(pk=manuscript.pk).update(
        root_folder=root, main_file_node=main_node
    )


@receiver(post_save, sender="writing.ManuscriptFile")
def manuscript_file_saved(sender, instance, **kwargs):
    _resync(instance.manuscript)


@receiver(post_delete, sender="writing.ManuscriptFile")
def manuscript_file_deleted(sender, instance, **kwargs):
    from .models import Manuscript

    # during a manuscript cascade-delete the parent may already be gone — skip then
    manuscript = Manuscript.objects.filter(pk=instance.manuscript_id).first()
    if manuscript is not None:
        _resync(manuscript)
