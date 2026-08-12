"""Split a pathway at intermediate structures into per-hop pathways.

The default run is a dry-run preview: it detects candidate structures
within the tolerance of the pathway's line and prints them ordered by
chainage, together with the resulting hop layout and any warnings.
Re-run with --apply to execute the split atomically.
"""

from django.core.management.base import BaseCommand, CommandError

from netbox_pathways.models import Pathway, Structure
from netbox_pathways.split import (
    DEFAULT_TOLERANCE,
    SplitError,
    execute_split,
    find_candidates,
    plan_split,
)


class Command(BaseCommand):
    help = "Split a pathway at intermediate structures into per-hop pathways."

    def add_arguments(self, parser):
        parser.add_argument("pathway_pk", type=int, help="PK of the pathway to split")
        parser.add_argument(
            "--tolerance",
            type=float,
            default=DEFAULT_TOLERANCE,
            help="Detection tolerance in SRID units (metres on projected SRIDs); default %(default)s",
        )
        parser.add_argument(
            "--structures",
            type=int,
            nargs="+",
            metavar="ID",
            help="Split at exactly these structure PKs instead of detecting candidates",
        )
        parser.add_argument(
            "--exclude",
            type=int,
            nargs="+",
            metavar="ID",
            default=[],
            help="Structure PKs to drop from the detected candidates",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Execute the split (without this flag the command only previews)",
        )

    def handle(self, *args, **options):
        try:
            pathway = Pathway.objects.get(pk=options["pathway_pk"])
        except Pathway.DoesNotExist:
            raise CommandError(f"Pathway {options['pathway_pk']} does not exist.") from None

        tolerance = options["tolerance"]
        try:
            structures = self._resolve_structures(pathway, options, tolerance)
            plan = plan_split(pathway, structures, tolerance)
        except SplitError as exc:
            raise CommandError(str(exc)) from None

        self._print_plan(plan)
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run -- re-run with --apply to execute."))
            return

        result = execute_split(plan)
        self._print_result(result)

    def _resolve_structures(self, pathway, options, tolerance):
        if options["structures"]:
            structures = list(Structure.objects.filter(pk__in=options["structures"]))
            missing = set(options["structures"]) - {s.pk for s in structures}
            if missing:
                raise CommandError(f"Structure PK(s) not found: {sorted(missing)}")
            return structures
        candidates = find_candidates(pathway, tolerance)
        excluded = set(options["exclude"])
        return [c.structure for c in candidates if c.structure.pk not in excluded]

    def _print_plan(self, plan):
        pathway = plan.pathway
        self.stdout.write(f"Pathway: {pathway} ({pathway.pathway_type}, pk {pathway.pk})")
        self.stdout.write("Split structures (ordered along the path):")
        self.stdout.write(f"  {'pk':>8}  {'chainage':>10}  {'offset':>8}  name")
        for cut in plan.cuts:
            self.stdout.write(f"  {cut.structure.pk:>8}  {cut.chainage:>10.2f}  {cut.offset:>8.2f}  {cut.structure}")
        hops = [
            str(pathway.start_endpoint or "?"),
            *(str(cut.structure) for cut in plan.cuts),
            str(pathway.end_endpoint or "?"),
        ]
        self.stdout.write("Resulting hops: " + " -> ".join(hops))
        for warning in plan.warnings:
            self.stdout.write(self.style.WARNING(f"WARNING: {warning}"))

    def _print_result(self, result):
        self.stdout.write(self.style.SUCCESS(f"Created {len(result.children)} pathways:"))
        for child in result.children:
            self.stdout.write(
                f"  pk {child.pk}: {child} ({child.start_endpoint} -> {child.end_endpoint}, "
                f"{child.geo_length or '?'} m)"
            )
        for original, copies in result.cascaded:
            self.stdout.write(f"  cascaded {type(original).__name__} into {len(copies)} per-hop copies")
        for cable, segments in result.rerouted:
            self.stdout.write(f"  re-routed cable {cable} across {len(segments)} segments")
