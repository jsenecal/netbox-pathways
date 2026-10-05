"""Put pathway ends back on the structures they are attached to.

Saving a structure drags its pathway ends along, but writes that bypass
save() -- queryset update(), bulk_update, raw SQL, a restored dump -- leave
them behind. This command finds pathway ends farther than the endpoint
tolerance from their structure or junction, and aerial spans that are bent
or detached. The default run only reports; --apply repairs atomically.
Detached aerial spans are reported but cannot be repaired: there is no
structure to land on.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from netbox_pathways.choices import PathwayTypeChoices
from netbox_pathways.management.commands._common import (
    add_apply_argument,
    add_user_argument,
    resolve_structures,
    resolve_user,
    tracked,
)
from netbox_pathways.models import Pathway
from netbox_pathways.reanchor import find_drift, pathways_anchored_to, repair


class Command(BaseCommand):
    help = "Find and repair pathway ends that no longer sit on their structure."

    def add_arguments(self, parser):
        parser.add_argument(
            "--structure",
            type=int,
            nargs="+",
            metavar="ID",
            default=[],
            help="Only check pathways attached to these structure PKs",
        )
        parser.add_argument(
            "--type",
            nargs="+",
            choices=PathwayTypeChoices.values(),
            default=[],
            help="Only check pathways of these types",
        )
        add_apply_argument(parser, "Repair what was found (without this flag the command only reports)")
        add_user_argument(parser, "repair")

    def handle(self, *args, **options):
        user = resolve_user(options["user"])
        drifts = find_drift(self._pathways(options))

        for drift in drifts:
            pathway = drift.pathway
            self.stdout.write(
                f"Pathway {pathway} ({pathway.pathway_type}, pk {pathway.pk}): " + "; ".join(drift.problems)
            )
        if not drifts:
            self.stdout.write(self.style.SUCCESS("All pathway ends sit on their anchors."))
            return
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(f"Dry run -- {len(drifts)} pathway(s) found; re-run with --apply."))
            return

        repairable = [drift for drift in drifts if drift.repairable]
        with tracked(user), transaction.atomic():
            for drift in repairable:
                repair(drift.pathway)
        attention = len(drifts) - len(repairable)
        self.stdout.write(
            self.style.SUCCESS(f"Repaired {len(repairable)} pathway(s); {attention} need(s) attention in the UI.")
        )

    def _pathways(self, options):
        pathways = Pathway.objects.order_by("pk")
        if options["type"]:
            pathways = pathways.filter(pathway_type__in=options["type"])
        if options["structure"]:
            pks = set()
            for structure in resolve_structures(options["structure"]):
                pks.update(pathways_anchored_to(structure).values_list("pk", flat=True))
            pathways = pathways.filter(pk__in=pks)
        return pathways
