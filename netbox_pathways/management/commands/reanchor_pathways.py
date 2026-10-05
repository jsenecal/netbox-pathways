"""Put pathway ends back on the structures they are attached to.

Saving a structure drags its pathway ends along, but writes that bypass
save() -- queryset update(), bulk_update, raw SQL, a restored dump -- leave
them behind. This command finds pathway ends farther than the endpoint
tolerance from their structure or junction, and aerial spans that are bent
or detached. The default run only reports; --apply repairs atomically.
Detached aerial spans are reported but cannot be repaired: there is no
structure to land on.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from netbox_pathways.choices import PathwayTypeChoices
from netbox_pathways.management.commands._tracking import add_user_argument, resolve_user, tracked
from netbox_pathways.models import Pathway, Structure
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
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Repair what was found (without this flag the command only reports)",
        )
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

        with tracked(user), transaction.atomic():
            for drift in drifts:
                repair(drift.pathway)
        self.stdout.write(self.style.SUCCESS(f"Repaired {len(drifts)} pathway(s)."))

    def _pathways(self, options):
        pathways = Pathway.objects.order_by("pk")
        if options["type"]:
            pathways = pathways.filter(pathway_type__in=options["type"])
        if options["structure"]:
            structures = list(Structure.objects.filter(pk__in=options["structure"]))
            missing = set(options["structure"]) - {s.pk for s in structures}
            if missing:
                raise CommandError(f"Structure PK(s) not found: {sorted(missing)}")
            pks = set()
            for structure in structures:
                pks.update(pathways_anchored_to(structure).values_list("pk", flat=True))
            pathways = pathways.filter(pk__in=pks)
        return pathways
