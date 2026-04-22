"""Generate 500+ sample records for each netbox_pathways model.

Usage:
    python manage.py generate_sample_data
    python manage.py generate_sample_data --flush   # delete existing sample data first
"""

import random

from dcim.models import Cable, Location, Site
from django.contrib.gis.geos import LineString, Point
from django.core.management.base import BaseCommand
from tenancy.models import Tenant

from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    CableSegment,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    Pathway,
    PathwayLocation,
    SiteGeometry,
    SlackLoop,
    Structure,
)

# Storage SRID from plugin config (3348 = NAD83 CSRS Lambert).
# Coordinates are generated in WGS84 then transformed to storage SRID.
STORAGE_SRID = get_srid()
WGS84 = 4326

# --- Montreal-area bounding box in WGS84 (lon/lat) ---
# We generate in WGS84 then transform to storage SRID.
MTL_LON_MIN, MTL_LON_MAX = -73.75, -73.45
MTL_LAT_MIN, MTL_LAT_MAX = 45.42, 45.58

STRUCTURE_TYPES = [
    'pole', 'manhole', 'handhole', 'cabinet', 'vault', 'pedestal',
    'building_entrance', 'splice_closure', 'tower', 'roof',
    'equipment_room', 'telecom_closet', 'riser_room',
]

CONDUIT_MATERIALS = ['pvc', 'hdpe', 'steel', 'concrete', 'fiberglass']
AERIAL_TYPES = ['messenger', 'self_support', 'lashed', 'wrapped', 'adss']
BANK_CONFIGS = ['1x2', '1x3', '1x4', '2x2', '2x3', '3x3', '3x4', 'custom']
ENCASEMENT_TYPES = ['concrete', 'direct_buried', 'bore', 'bridge_attachment', 'tunnel']
INNERDUCT_SIZES = ['1.25"', '1"', '32mm', '25mm', '1.5"']
INNERDUCT_COLORS = ['orange', 'blue', 'green', 'red', 'yellow', 'white', 'black']

CITY_NAMES = [
    'Montreal', 'Laval', 'Longueuil', 'Brossard', 'Terrebonne',
    'Saint-Jerome', 'Repentigny', 'Blainville', 'Mirabel', 'Candiac',
]

STREET_NAMES = [
    'Sainte-Catherine', 'Saint-Laurent', 'Sherbrooke', 'Mont-Royal',
    'Papineau', 'Berri', 'Pie-IX', 'Jean-Talon', 'Notre-Dame',
    'Rene-Levesque', 'Atwater', 'Guy', 'Peel', 'McGill',
    'University', 'Crescent', 'Bishop', 'Mackay', 'Drummond',
    'Stanley', 'Mansfield', 'Metcalfe', 'Bleury', 'Clark',
]


def _rand_point():
    """Random point in the Montreal area, stored in the configured SRID."""
    lon = random.uniform(MTL_LON_MIN, MTL_LON_MAX)
    lat = random.uniform(MTL_LAT_MIN, MTL_LAT_MAX)
    pt = Point(lon, lat, srid=WGS84)
    if STORAGE_SRID != WGS84:
        pt.transform(STORAGE_SRID)
    return pt


def _line_between(p1, p2, jitter=True):
    """Create a LineString between two points, optionally with mid-point jitter.

    Works in the storage SRID coordinate space.
    """
    coords = [p1.coords]
    if jitter:
        # For projected SRIDs (meters), jitter ~300m; for WGS84 (degrees), ~0.003°
        jitter_scale = 300 if STORAGE_SRID != WGS84 else 0.003
        mid_x = (p1.x + p2.x) / 2 + random.uniform(-jitter_scale, jitter_scale)
        mid_y = (p1.y + p2.y) / 2 + random.uniform(-jitter_scale, jitter_scale)
        coords.append((mid_x, mid_y))
    coords.append(p2.coords)
    return LineString(coords, srid=STORAGE_SRID)


class Command(BaseCommand):
    help = 'Generate 500+ sample records for each netbox_pathways model.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete all existing pathways data before generating.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()

        self.stdout.write('Creating prerequisite data...')
        sites = self._create_sites()
        tenants = self._create_tenants()
        locations = self._create_locations(sites)

        self.stdout.write('Creating structures (600)...')
        structures = self._create_structures(sites, tenants)

        self.stdout.write('Creating conduit banks (500)...')
        banks = self._create_conduit_banks(structures, tenants)

        self.stdout.write('Creating conduits (600)...')
        conduits = self._create_conduits(structures, banks, tenants)

        self.stdout.write('Creating aerial spans (500)...')
        aerial_spans = self._create_aerial_spans(structures, tenants)

        self.stdout.write('Creating direct buried (500)...')
        direct_buried = self._create_direct_buried(structures, tenants)

        self.stdout.write('Creating innerducts (500)...')
        self._create_innerducts(conduits)

        self.stdout.write('Creating conduit junctions (200)...')
        self._create_conduit_junctions(conduits, structures)

        self.stdout.write('Creating cables (300)...')
        cables = self._create_cables()

        # Gather all pathways for cable segments and pathway locations
        all_pathways = list(
            Pathway.objects.filter(
                pk__in=[c.pk for c in conduits]
                + [a.pk for a in aerial_spans]
                + [d.pk for d in direct_buried]
            )
        )

        self.stdout.write('Creating cable segments (500)...')
        self._create_cable_segments(cables, all_pathways)

        self.stdout.write('Creating slack loops (100)...')
        self._create_slack_loops(cables, structures, all_pathways)

        self.stdout.write('Creating pathway locations (500)...')
        self._create_pathway_locations(all_pathways, sites, locations)

        self.stdout.write('Creating site geometries...')
        self._create_site_geometries(sites, structures)

        self.stdout.write(self.style.SUCCESS('\nSample data generation complete!'))
        self._print_counts()

    def _flush(self):
        self.stdout.write(self.style.WARNING('Flushing existing pathways data...'))
        SlackLoop.objects.all().delete()
        CableSegment.objects.all().delete()
        PathwayLocation.objects.all().delete()
        ConduitJunction.objects.all().delete()
        Innerduct.objects.all().delete()
        DirectBuried.objects.all().delete()
        AerialSpan.objects.all().delete()
        Conduit.objects.all().delete()
        ConduitBank.objects.all().delete()
        SiteGeometry.objects.all().delete()
        Structure.objects.all().delete()
        # Clean up sample prerequisite data
        Cable.objects.filter(label__startswith='CBL-SAMPLE-').delete()
        Location.objects.filter(name__startswith='Sample ').delete()
        Site.objects.filter(name__startswith='Site-').delete()
        Tenant.objects.filter(name__startswith='Tenant-').delete()

    def _create_sites(self):
        sites = []
        for _i, city in enumerate(CITY_NAMES):
            name = f'Site-{city}'
            site, _ = Site.objects.get_or_create(
                name=name, defaults={'slug': f'site-{city.lower().replace(" ", "-")}'},
            )
            sites.append(site)
        return sites

    def _create_tenants(self):
        names = [
            'Tenant-Bell', 'Tenant-Telus', 'Tenant-Videotron',
            'Tenant-Rogers', 'Tenant-Cogeco', 'Tenant-Fibrenoire',
        ]
        tenants = []
        for name in names:
            t, _ = Tenant.objects.get_or_create(
                name=name, defaults={'slug': name.lower()},
            )
            tenants.append(t)
        return tenants

    def _create_locations(self, sites):
        locations = []
        for site in sites[:5]:
            for j in range(5):
                name = f'Sample Bldg {site.name}-{j+1}'
                loc, _ = Location.objects.get_or_create(
                    name=name, site=site,
                    defaults={'slug': f'sample-bldg-{site.pk}-{j+1}'},
                )
                locations.append(loc)
        return locations

    def _create_structures(self, sites, tenants):
        structures = []
        batch = []
        for i in range(600):
            site = random.choice(sites)
            stype = random.choice(STRUCTURE_TYPES)
            tenant = random.choice(tenants) if random.random() < 0.7 else None
            name = f'{stype.replace("_", " ").title()} {random.choice(STREET_NAMES)}-{i+1:04d}'
            batch.append(Structure(
                name=name,
                structure_type=stype,
                site=site,
                location=_rand_point(),
                elevation=round(random.uniform(10, 200), 1) if random.random() < 0.5 else None,
                installation_date=f'{random.randint(1990, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}' if random.random() < 0.6 else None,
                tenant=tenant,
                access_notes=f'Access via {random.choice(STREET_NAMES)}' if random.random() < 0.3 else '',
            ))
        structures = Structure.objects.bulk_create(batch, ignore_conflicts=False)
        return structures

    def _create_conduit_banks(self, structures, tenants):
        # Pick structures that are manholes/handholes/vaults
        eligible = [s for s in structures if s.structure_type in ('manhole', 'handhole', 'vault', 'building_entrance')]
        if len(eligible) < 100:
            eligible = structures[:200]
        faces = ['north', 'south', 'east', 'west', 'other']
        banks = []
        for i in range(500):
            s1, s2 = random.sample(eligible, 2)
            config = random.choice(BANK_CONFIGS)
            enc = random.choice(ENCASEMENT_TYPES) if random.random() < 0.6 else ''
            if config == 'custom':
                total = random.randint(1, 12)
            else:
                rows, cols = config.split('x')
                total = int(rows) * int(cols)
            banks.append(ConduitBank(
                label=f'Bank-{i+1:04d}',
                path=_line_between(s1.location, s2.location),
                start_structure=s1,
                end_structure=s2,
                start_face=random.choice(faces),
                end_face=random.choice(faces),
                tenant=random.choice(tenants) if random.random() < 0.5 else None,
                configuration=config,
                total_conduits=total,
                encasement_type=enc,
                installation_date=f'{random.randint(1995, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}' if random.random() < 0.5 else None,
            ))
        return ConduitBank.objects.bulk_create(banks)

    def _create_conduits(self, structures, banks, tenants):
        conduits = []
        used_bank_positions = set()
        for i in range(600):
            s1, s2 = random.sample(structures, 2)
            path = _line_between(s1.location, s2.location)
            bank = random.choice(banks) if random.random() < 0.3 else None
            bank_pos = ''
            if bank:
                # Generate unique position per bank
                for _ in range(20):
                    pos = f'{chr(65 + random.randint(0, 5))}{random.randint(1, 6)}'
                    if (bank.pk, pos) not in used_bank_positions:
                        bank_pos = pos
                        used_bank_positions.add((bank.pk, pos))
                        break
                else:
                    bank = None  # no free position, skip bank assignment
            mat = random.choice(CONDUIT_MATERIALS)
            conduits.append(Conduit(
                label=f'CDT-{i+1:04d}',
                path=path,
                start_structure=s1,
                end_structure=s2,
                tenant=random.choice(tenants) if random.random() < 0.5 else None,
                material=mat,
                inner_diameter=round(random.uniform(25, 150), 1),
                outer_diameter=round(random.uniform(30, 170), 1),
                depth=round(random.uniform(0.5, 3.0), 2) if random.random() < 0.7 else None,
                length=round(random.uniform(20, 2000), 1),
                conduit_bank=bank,
                bank_position=bank_pos,
                installation_date=f'{random.randint(1995, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}' if random.random() < 0.5 else None,
            ))
        created = []
        for c in conduits:
            c.save()
            created.append(c)
        return created

    def _create_aerial_spans(self, structures, tenants):
        spans = []
        pole_structures = [s for s in structures if s.structure_type == 'pole']
        if len(pole_structures) < 50:
            pole_structures = structures[:200]
        for i in range(500):
            s1, s2 = random.sample(pole_structures, 2)
            path = _line_between(s1.location, s2.location)
            spans.append(AerialSpan(
                label=f'AER-{i+1:04d}',
                path=path,
                start_structure=s1,
                end_structure=s2,
                tenant=random.choice(tenants) if random.random() < 0.4 else None,
                aerial_type=random.choice(AERIAL_TYPES),
                attachment_height=round(random.uniform(5, 15), 1),
                sag=round(random.uniform(0.3, 3.0), 2) if random.random() < 0.6 else None,
                messenger_size=f'{random.choice(["6M", "10M", "1/4 EHS", "3/8 EHS"])}' if random.random() < 0.5 else '',
                length=round(random.uniform(30, 500), 1),
                installation_date=f'{random.randint(2000, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}' if random.random() < 0.5 else None,
            ))
        created = []
        for s in spans:
            s.save()
            created.append(s)
        return created

    def _create_direct_buried(self, structures, tenants):
        dbs = []
        for i in range(500):
            s1, s2 = random.sample(structures, 2)
            path = _line_between(s1.location, s2.location)
            dbs.append(DirectBuried(
                label=f'DB-{i+1:04d}',
                path=path,
                start_structure=s1,
                end_structure=s2,
                tenant=random.choice(tenants) if random.random() < 0.4 else None,
                burial_depth=round(random.uniform(0.6, 2.5), 2),
                warning_tape=random.random() < 0.7,
                tracer_wire=random.random() < 0.5,
                armor_type=random.choice(['steel tape', 'corrugated steel', 'aluminum', '']) if random.random() < 0.4 else '',
                length=round(random.uniform(50, 3000), 1),
                installation_date=f'{random.randint(2000, 2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}' if random.random() < 0.5 else None,
            ))
        created = []
        for d in dbs:
            d.save()
            created.append(d)
        return created

    def _create_innerducts(self, conduits):
        innerducts = []
        for i in range(500):
            parent = random.choice(conduits)
            innerducts.append(Innerduct(
                label=f'ID-{i+1:04d}',
                path=parent.path,
                parent_conduit=parent,
                size=random.choice(INNERDUCT_SIZES),
                color=random.choice(INNERDUCT_COLORS),
                position=f'{random.randint(1, 4)}' if random.random() < 0.6 else '',
                length=parent.length,
            ))
        created = []
        for idc in innerducts:
            idc.save()
            created.append(idc)
        return created

    def _create_conduit_junctions(self, conduits, structures):
        junctions = []
        used_positions = set()
        attempts = 0
        while len(junctions) < 200 and attempts < 1000:
            attempts += 1
            trunk = random.choice(conduits)
            branch = random.choice(conduits)
            if trunk.pk == branch.pk:
                continue
            if not trunk.start_structure or not trunk.end_structure:
                continue
            towards = random.choice([trunk.start_structure, trunk.end_structure])
            pos = round(random.uniform(0.1, 0.9), 2)
            key = (trunk.pk, pos)
            if key in used_positions:
                continue
            used_positions.add(key)
            junctions.append(ConduitJunction(
                label=f'JCT-{len(junctions)+1:04d}',
                trunk_conduit=trunk,
                branch_conduit=branch,
                towards_structure=towards,
                position_on_trunk=pos,
            ))
        return ConduitJunction.objects.bulk_create(junctions)

    def _create_cables(self):
        cables = []
        for i in range(300):
            cables.append(Cable(
                label=f'CBL-SAMPLE-{i+1:04d}',
                type=random.choice(['cat6a', 'smf-os2', 'mmf-om4', 'smf', 'cat6']),
                length=round(random.uniform(50, 5000), 1),
                length_unit='m',
            ))
        Cable.objects.bulk_create(cables, ignore_conflicts=True)
        # Re-fetch to get PKs (bulk_create with ignore_conflicts doesn't set them)
        return list(Cable.objects.filter(label__startswith='CBL-SAMPLE-'))

    def _create_cable_segments(self, cables, pathways):
        if not pathways:
            self.stdout.write(self.style.WARNING('  No pathways available for cable segments.'))
            return []
        segments = []
        for _i in range(500):
            cable = random.choice(cables)
            pathway = random.choice(pathways)
            segments.append(CableSegment(
                cable=cable,
                pathway=pathway,
            ))
        return CableSegment.objects.bulk_create(segments)

    def _create_slack_loops(self, cables, structures, pathways):
        if not cables or not structures:
            self.stdout.write(self.style.WARNING('  No cables/structures available for slack loops.'))
            return []
        loops = []
        for _i in range(100):
            cable = random.choice(cables)
            structure = random.choice(structures)
            length = round(random.uniform(1, 15), 1)
            # ~20% have a pathway reference (aerial slack)
            pathway = random.choice(pathways) if pathways and random.random() < 0.2 else None
            loops.append(SlackLoop(
                cable=cable,
                structure=structure,
                pathway=pathway,
                length=length,
            ))
        return SlackLoop.objects.bulk_create(loops)

    def _create_pathway_locations(self, pathways, sites, locations):
        if not pathways:
            return []
        waypoints = []
        used_keys = set()
        for _i in range(500):
            pathway = random.choice(pathways)
            seq = random.randint(0, 10)
            key = (pathway.pk, seq)
            while key in used_keys:
                seq += 1
                key = (pathway.pk, seq)
            used_keys.add(key)
            site = random.choice(sites) if random.random() < 0.5 else None
            location = random.choice(locations) if locations and random.random() < 0.5 else None
            if not site and not location:
                site = random.choice(sites)
            waypoints.append(PathwayLocation(
                pathway=pathway,
                site=site,
                location=location,
                sequence=seq,
            ))
        return PathwayLocation.objects.bulk_create(waypoints)

    def _create_site_geometries(self, sites, structures):
        for site in sites:
            site_structs = [s for s in structures if s.site_id == site.pk]
            struct = site_structs[0] if site_structs else None
            SiteGeometry.objects.get_or_create(
                site=site,
                defaults={
                    'structure': struct,
                    'geometry': struct.location if struct else _rand_point(),
                },
            )

    def _print_counts(self):
        self.stdout.write(f'  Structures:         {Structure.objects.count()}')
        self.stdout.write(f'  Conduit Banks:      {ConduitBank.objects.count()}')
        self.stdout.write(f'  Conduits:           {Conduit.objects.count()}')
        self.stdout.write(f'  Aerial Spans:       {AerialSpan.objects.count()}')
        self.stdout.write(f'  Direct Buried:      {DirectBuried.objects.count()}')
        self.stdout.write(f'  Innerducts:         {Innerduct.objects.count()}')
        self.stdout.write(f'  Conduit Junctions:  {ConduitJunction.objects.count()}')
        self.stdout.write(f'  Cables:             {Cable.objects.filter(label__startswith="CBL-SAMPLE-").count()}')
        self.stdout.write(f'  Cable Segments:     {CableSegment.objects.count()}')
        self.stdout.write(f'  Slack Loops:        {SlackLoop.objects.count()}')
        self.stdout.write(f'  Pathway Locations:  {PathwayLocation.objects.count()}')
        self.stdout.write(f'  Site Geometries:    {SiteGeometry.objects.count()}')
