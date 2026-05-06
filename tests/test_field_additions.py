"""Tests for the FR#4 additive changes:

- ``Structure.installed_by`` and ``Pathway.installed_by`` -- FK to ``tenancy.Tenant``.
- ``Structure.commissioned_date`` and ``Pathway.commissioned_date`` -- DateField.
- ``StructureStatusChoices.STATUS_ABANDONED`` -- "Abandoned in place" status.

Written before any model changes; should fail (red) on the current main and
pass after the FR is implemented (green).
"""

from datetime import date

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.choices import StructureStatusChoices
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure

SRID = get_srid()


@pytest.fixture
def contractor(db):
    return Tenant.objects.create(name="Acme Splicing", slug="acme-splicing")


@pytest.fixture
def structure(db):
    return Structure.objects.create(name="P-001", location=Point(0, 0, srid=SRID))


@pytest.mark.django_db
class TestStructureFieldAdditions:
    def test_installed_by_fk_to_tenant(self, contractor):
        s = Structure.objects.create(
            name="P-INS-1",
            location=Point(1, 1, srid=SRID),
            installed_by=contractor,
        )
        s.refresh_from_db()
        assert s.installed_by_id == contractor.pk
        assert s.installed_by.name == "Acme Splicing"

    def test_installed_by_optional(self):
        s = Structure.objects.create(name="P-INS-2", location=Point(2, 2, srid=SRID))
        assert s.installed_by is None

    def test_commissioned_date_stored(self, contractor):
        s = Structure.objects.create(
            name="P-INS-3",
            location=Point(3, 3, srid=SRID),
            installed_by=contractor,
            commissioned_date=date(2025, 4, 9),
        )
        s.refresh_from_db()
        assert s.commissioned_date == date(2025, 4, 9)

    def test_commissioned_date_optional(self):
        s = Structure.objects.create(name="P-INS-4", location=Point(4, 4, srid=SRID))
        assert s.commissioned_date is None


@pytest.mark.django_db
class TestPathwayFieldAdditions:
    def _path(self):
        return LineString((0, 0), (10, 10), srid=SRID)

    def test_installed_by_fk_to_tenant(self, contractor):
        pw = Pathway.objects.create(
            path=self._path(),
            pathway_type="conduit",
            installed_by=contractor,
        )
        pw.refresh_from_db()
        assert pw.installed_by_id == contractor.pk

    def test_installed_by_optional(self):
        pw = Pathway.objects.create(path=self._path(), pathway_type="conduit")
        assert pw.installed_by is None

    def test_commissioned_date_stored(self):
        pw = Pathway.objects.create(
            path=self._path(),
            pathway_type="conduit",
            commissioned_date=date(2025, 4, 9),
        )
        pw.refresh_from_db()
        assert pw.commissioned_date == date(2025, 4, 9)


class TestAbandonedStatus:
    def test_status_value_present(self):
        assert StructureStatusChoices.STATUS_ABANDONED == "abandoned"

    def test_status_label_is_abandoned_in_place(self):
        labels = {value: label for value, label, *_ in StructureStatusChoices.CHOICES}
        assert labels.get("abandoned") == "Abandoned in place"

    def test_status_has_color(self):
        colors = StructureStatusChoices.colors
        assert colors.get("abandoned") == "gray"

    @pytest.mark.django_db
    def test_structure_can_be_saved_with_abandoned_status(self):
        s = Structure.objects.create(
            name="P-AB-1",
            location=Point(7, 7, srid=SRID),
            status=StructureStatusChoices.STATUS_ABANDONED,
        )
        s.refresh_from_db()
        assert s.status == "abandoned"
