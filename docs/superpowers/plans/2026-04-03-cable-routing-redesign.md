# Cable Routing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify CableSegment (auto-managed sequence, remove slack fields), create SlackLoop model, add route validation, enhance cable detail page, gate pull sheets on valid routes, and reorganize navigation.

**Architecture:** CableSegment becomes a lean through-table (cable → pathway + auto-sequence). SlackLoop is a new model for slack at structures. Route validation in `routing.py` checks consecutive segments share endpoints. Template extensions on `dcim.cable` show route status and slack. Pull sheets gated on valid routes.

**Tech Stack:** Django 5.2, NetBox 4.5, PostGIS, pytest

**Spec:** `docs/superpowers/specs/2026-04-03-cable-routing-redesign.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `netbox_pathways/routing.py` | Route validation: `validate_cable_route()` |
| `tests/test_routing.py` | Tests for route validation |
| `tests/test_slack_loop.py` | Tests for SlackLoop model |
| `tests/test_cable_segment.py` | Tests for CableSegment sequence auto-assignment |
| `netbox_pathways/migrations/0007_cable_routing_redesign.py` | Auto-generated migration |
| `templates/netbox_pathways/inc/cable_route_status.html` | Route status panel include template |

### Modified files
| File | Changes |
|------|---------|
| `models.py` | CableSegment: remove slack fields, add sequence + constraint + `save()` override. Add SlackLoop model. |
| `forms.py` | CableSegment: remove slack fields/widgets. Add SlackLoopForm. |
| `tables.py` | CableSegment: remove slack column. Add SlackLoopTable. |
| `filters.py` | Add SlackLoopFilterSet. |
| `search.py` | Add SlackLoopIndex. |
| `ui/panels.py` | CableSegment: remove slack attr. Add SlackLoopPanel. |
| `api/serializers.py` | CableSegment: remove slack fields, add sequence. Add SlackLoopSerializer. |
| `api/views.py` | Add SlackLoopViewSet. |
| `api/urls.py` | Register slack-loops route. |
| `views.py` | Add SlackLoop views. Update pull sheet views with route gating + slack from SlackLoop. |
| `urls.py` | Add SlackLoop URL patterns. |
| `navigation.py` | New "Cable Routing" group with Cable Segments, Slack Loops, Pull Sheets. |
| `routing.py` | New file — `validate_cable_route()`. |
| `template_content.py` | Add route status panel. Modify CableRouteMapExtension. Add SlackLoop panels on Cable/Structure. |
| `templates/netbox_pathways/pullsheet_detail.html` | Remove per-segment slack column. Add slack section from SlackLoop. Gate on valid route. |

---

## Task 1: CableSegment Model Changes

**Files:**
- Modify: `netbox_pathways/models.py:462-484`
- Test: `tests/test_cable_segment.py` (create)

- [ ] **Step 1: Write failing tests for CableSegment changes**

Create `tests/test_cable_segment.py`:

```python
import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString
from django.db import IntegrityError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure


@pytest.mark.django_db
class TestCableSegmentSequence:
    @pytest.fixture
    def structures(self):
        return [
            Structure.objects.create(name=f"MH-{i}") for i in range(3)
        ]

    @pytest.fixture
    def pathway(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            name="C-1",
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    @pytest.fixture
    def pathway2(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            name="C-2",
            start_structure=structures[1],
            end_structure=structures[2],
            path=LineString((1, 1), (2, 2), srid=srid),
        )

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-001")

    def test_auto_sequence_first_segment(self, cable, pathway):
        seg = CableSegment(cable=cable, pathway=pathway)
        seg.save()
        assert seg.sequence == 1

    def test_auto_sequence_increments(self, cable, pathway, pathway2):
        seg1 = CableSegment.objects.create(cable=cable, pathway=pathway)
        seg2 = CableSegment(cable=cable, pathway=pathway2)
        seg2.save()
        assert seg1.sequence == 1
        assert seg2.sequence == 2

    def test_sequence_unique_per_cable(self, cable, pathway, pathway2):
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)
        with pytest.raises(IntegrityError):
            CableSegment.objects.create(cable=cable, pathway=pathway2, sequence=1)

    def test_explicit_sequence_respected(self, cable, pathway):
        seg = CableSegment(cable=cable, pathway=pathway, sequence=10)
        seg.save()
        assert seg.sequence == 10

    def test_no_slack_fields(self):
        """slack_loop_location and slack_length should not exist on model."""
        field_names = [f.name for f in CableSegment._meta.get_fields()]
        assert 'slack_loop_location' not in field_names
        assert 'slack_length' not in field_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_cable_segment.py -v`
Expected: Multiple failures (slack fields still exist, sequence doesn't exist yet)

- [ ] **Step 3: Update CableSegment model**

In `netbox_pathways/models.py`, replace the CableSegment class (lines 462-484):

```python
class CableSegment(NetBoxModel):
    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='pathway_segments')
    pathway = models.ForeignKey(
        Pathway, on_delete=models.SET_NULL, null=True, blank=True, related_name='cable_segments',
    )
    sequence = models.PositiveIntegerField(
        null=True, blank=True, help_text="Order of segment in cable route (auto-assigned)",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['cable', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['cable', 'sequence'],
                name='unique_cable_segment_sequence',
            ),
        ]

    def __str__(self):
        pw = self.pathway
        if pw:
            return f"{self.cable.label} → {pw.name}"
        return f"{self.cable.label} - Segment {self.pk}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:cablesegment', args=[self.pk])

    def save(self, *args, **kwargs):
        if self.sequence is None:
            max_seq = (
                CableSegment.objects
                .filter(cable=self.cable)
                .aggregate(m=models.Max('sequence'))['m']
            ) or 0
            self.sequence = max_seq + 1
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_cable_segment.py -v`
Expected: PASS (except migration not yet created — tests may need `--create-db`)

- [ ] **Step 5: Commit**

**Note:** Do NOT run `makemigrations` yet — wait until Task 2 so a single migration captures both CableSegment changes and the new SlackLoop model.

```
feat(models): simplify CableSegment — auto-managed sequence, remove slack fields
```

---

## Task 2: SlackLoop Model

**Files:**
- Modify: `netbox_pathways/models.py` (append after CableSegment)
- Test: `tests/test_slack_loop.py` (create)

- [ ] **Step 1: Write failing tests for SlackLoop**

Create `tests/test_slack_loop.py`:

```python
import pytest
from dcim.models import Cable

from netbox_pathways.models import SlackLoop, Structure


@pytest.mark.django_db
class TestSlackLoop:
    @pytest.fixture
    def structure(self):
        return Structure.objects.create(name="MH-SL-1")

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-SL-001")

    def test_create_underground_slack(self, cable, structure):
        sl = SlackLoop.objects.create(
            cable=cable, structure=structure, length=3.5,
        )
        assert sl.pk is not None
        assert sl.pathway is None
        assert sl.length == 3.5

    def test_structure_required(self, cable):
        with pytest.raises(Exception):
            SlackLoop.objects.create(cable=cable, structure=None, length=1.0)

    def test_str_representation(self, cable, structure):
        sl = SlackLoop.objects.create(
            cable=cable, structure=structure, length=5.0,
        )
        assert cable.label in str(sl)
        assert structure.name in str(sl)

    def test_multiple_per_cable_structure(self, cable, structure):
        """Multiple slack loops at the same structure are valid."""
        sl1 = SlackLoop.objects.create(cable=cable, structure=structure, length=3.0)
        sl2 = SlackLoop.objects.create(cable=cable, structure=structure, length=2.0)
        assert sl1.pk != sl2.pk
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_slack_loop.py -v`
Expected: ImportError — SlackLoop doesn't exist yet

- [ ] **Step 3: Add SlackLoop model**

Append to `netbox_pathways/models.py` after CableSegment:

```python
class SlackLoop(NetBoxModel):
    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='slack_loops')
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE, related_name='slack_loops')
    pathway = models.ForeignKey(
        Pathway, on_delete=models.SET_NULL, null=True, blank=True, related_name='slack_loops',
        help_text="For aerial slack stored on a span near the structure",
    )
    length = models.FloatField(help_text="Length of slack in meters")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['cable', 'structure']

    def __str__(self):
        return f"{self.cable.label} — {self.length}m @ {self.structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:slackloop', args=[self.pk])
```

- [ ] **Step 4: Generate and apply migration**

Run:
```bash
cd /opt/netbox/netbox && python manage.py makemigrations netbox_pathways --name cable_routing_redesign
cd /opt/netbox/netbox && python manage.py migrate netbox_pathways
```

- [ ] **Step 5: Run all model tests**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_cable_segment.py /opt/netbox-pathways/tests/test_slack_loop.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```
feat(models): add SlackLoop model for cable slack at structures
```

---

## Task 3: CRUD Layer — Forms, Tables, Filters, Search, Panels

**Files:**
- Modify: `netbox_pathways/forms.py:443-476`
- Modify: `netbox_pathways/tables.py:193-204`
- Modify: `netbox_pathways/filters.py:256-273`
- Modify: `netbox_pathways/search.py:98-103`
- Modify: `netbox_pathways/ui/panels.py:118-122`

- [ ] **Step 1: Update CableSegment form — remove slack fields, remove sequence**

In `forms.py`, update `CableSegmentForm`:
- Remove `slack_loop_location`, `slack_length` from fieldsets, fields, widgets
- `sequence` is NOT in forms (auto-managed)
- Fieldsets: just `FieldSet('cable', 'pathway', name='Cable Segment')` and `FieldSet('comments', 'tags', name='Details')`

Update `CableSegmentImportForm`:
- Remove `slack_length` from fields

- [ ] **Step 2: Add SlackLoopForm**

In `forms.py`, add after CableSegmentImportForm:

```python
class SlackLoopForm(NetBoxModelForm):
    cable = DynamicModelChoiceField(queryset=Cable.objects.all(), selector=True)
    structure = DynamicModelChoiceField(queryset=Structure.objects.all(), selector=True)
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(), required=False, selector=True,
    )

    fieldsets = (
        FieldSet('cable', 'structure', 'pathway', 'length', name='Slack Loop'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = SlackLoop
        fields = ['cable', 'structure', 'pathway', 'length', 'comments', 'tags']
```

- [ ] **Step 3: Update CableSegmentTable — remove slack column**

In `tables.py`, update `CableSegmentTable`:
- fields: `('pk', 'id', 'cable', 'pathway', 'sequence', 'actions')`
- default_columns: `('cable', 'pathway', 'sequence')`

- [ ] **Step 4: Add SlackLoopTable**

In `tables.py`:

```python
class SlackLoopTable(NetBoxTable):
    cable = tables.Column(linkify=True)
    structure = tables.Column(linkify=True)
    pathway = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = SlackLoop
        fields = ('pk', 'id', 'cable', 'structure', 'pathway', 'length', 'actions')
        default_columns = ('cable', 'structure', 'pathway', 'length')
```

- [ ] **Step 5: Add SlackLoopFilterSet**

In `filters.py`:

```python
class SlackLoopFilterSet(NetBoxModelFilterSet):
    cable_id = django_filters.ModelMultipleChoiceFilter(
        field_name='cable', queryset=Cable.objects.all(),
        label='Cable (ID)',
    )
    structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='structure', queryset=Structure.objects.all(),
        label='Structure (ID)',
    )
    pathway_id = django_filters.ModelMultipleChoiceFilter(
        field_name='pathway', queryset=Pathway.objects.all(),
        label='Pathway (ID)',
    )

    class Meta:
        model = SlackLoop
        fields = ['id']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(comments__icontains=value))
```

- [ ] **Step 6: Add SlackLoopIndex to search.py**

```python
@register_search
class SlackLoopIndex(SearchIndex):
    model = models.SlackLoop
    fields = (
        ('comments', 5000),
    )
    display_attrs = ('cable', 'structure', 'length')
```

- [ ] **Step 7: Update CableSegmentPanel, add SlackLoopPanel in ui/panels.py**

Update `CableSegmentPanel` — remove `slack_length`, add `sequence`:

```python
class CableSegmentPanel(ObjectAttributesPanel):
    cable = attrs.RelatedObjectAttr('cable', linkify=True, label=_('Cable'))
    pathway = attrs.RelatedObjectAttr('pathway', linkify=True, label=_('Pathway'))
    sequence = attrs.NumericAttr('sequence', label=_('Sequence'))
```

Add `SlackLoopPanel`:

```python
class SlackLoopPanel(ObjectAttributesPanel):
    cable = attrs.RelatedObjectAttr('cable', linkify=True, label=_('Cable'))
    structure = attrs.RelatedObjectAttr('structure', linkify=True, label=_('Structure'))
    pathway = attrs.RelatedObjectAttr('pathway', linkify=True, label=_('Pathway'))
    length = attrs.NumericAttr('length', label=_('Slack length (m)'))
```

- [ ] **Step 8: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: System check identified no issues

- [ ] **Step 9: Commit**

```
feat(crud): add SlackLoop CRUD layer — forms, tables, filters, search, panels
```

---

## Task 4: API Layer

**Files:**
- Modify: `netbox_pathways/api/serializers.py:178-191`
- Modify: `netbox_pathways/api/views.py:75-78`
- Modify: `netbox_pathways/api/urls.py`

- [ ] **Step 1: Update CableSegmentSerializer — remove slack, add sequence**

In `api/serializers.py`, update CableSegmentSerializer fields:

```python
fields = [
    'id', 'url', 'display', 'cable', 'pathway', 'sequence',
    'comments', 'tags', 'created', 'last_updated',
]
brief_fields = ('id', 'url', 'display', 'cable', 'pathway', 'sequence')
```

- [ ] **Step 2: Add SlackLoopSerializer**

```python
class SlackLoopSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:slackloop-detail',
    )

    class Meta:
        model = SlackLoop
        fields = [
            'id', 'url', 'display', 'cable', 'structure', 'pathway',
            'length', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'cable', 'structure', 'length')
```

- [ ] **Step 3: Add SlackLoopViewSet in api/views.py**

```python
class SlackLoopViewSet(NetBoxModelViewSet):
    queryset = models.SlackLoop.objects.select_related('cable', 'structure', 'pathway')
    serializer_class = serializers.SlackLoopSerializer
    filterset_class = filters.SlackLoopFilterSet
```

- [ ] **Step 4: Register route in api/urls.py**

Add: `router.register('slack-loops', views.SlackLoopViewSet)`

- [ ] **Step 5: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 6: Commit**

```
feat(api): add SlackLoop REST API endpoint
```

---

## Task 5: Views and URLs

**Files:**
- Modify: `netbox_pathways/views.py`
- Modify: `netbox_pathways/urls.py`

- [ ] **Step 1: Add SlackLoop views**

In `views.py`, add standard NetBox CRUD views for SlackLoop following the same pattern as other models (list, detail, edit, delete, bulk delete). Import SlackLoop model, form, table, filter.

```python
# --- Slack Loops ---

class SlackLoopListView(generic.ObjectListView):
    queryset = SlackLoop.objects.select_related('cable', 'structure', 'pathway')
    table = SlackLoopTable
    filterset = SlackLoopFilterSet
    filterset_form = None

class SlackLoopView(generic.ObjectView):
    queryset = SlackLoop.objects.all()
    layout = SimpleLayout(
        SlackLoopPanel(),
        TagsPanel(),
        CustomFieldsPanel(),
        CommentsPanel(),
    )

class SlackLoopEditView(generic.ObjectEditView):
    queryset = SlackLoop.objects.all()
    form = SlackLoopForm

class SlackLoopDeleteView(generic.ObjectDeleteView):
    queryset = SlackLoop.objects.all()

class SlackLoopBulkDeleteView(generic.BulkDeleteView):
    queryset = SlackLoop.objects.all()
    table = SlackLoopTable
```

- [ ] **Step 2: Add SlackLoop URL patterns in urls.py**

```python
# Slack Loops
path('slack-loops/', views.SlackLoopListView.as_view(), name='slackloop_list'),
path('slack-loops/add/', views.SlackLoopEditView.as_view(), name='slackloop_add'),
path('slack-loops/<int:pk>/', views.SlackLoopView.as_view(), name='slackloop'),
path('slack-loops/<int:pk>/edit/', views.SlackLoopEditView.as_view(), name='slackloop_edit'),
path('slack-loops/<int:pk>/delete/', views.SlackLoopDeleteView.as_view(), name='slackloop_delete'),
path('slack-loops/delete/', views.SlackLoopBulkDeleteView.as_view(), name='slackloop_bulk_delete'),
```

- [ ] **Step 3: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 4: Commit**

```
feat(views): add SlackLoop views and URL patterns
```

---

## Task 6: Navigation Reorganization

**Files:**
- Modify: `netbox_pathways/navigation.py`

- [ ] **Step 1: Reorganize menu groups**

Rewrite `navigation.py` to move Cable Segments and Pull Sheets out of Infrastructure/Tools into a new "Cable Routing" group, and add Slack Loops:

```
Infrastructure: Structures, Conduits, Aerial Spans, Direct Buried, Innerducts, Conduit Banks, Junctions
Cable Routing:  Cable Segments, Slack Loops, Pull Sheets
GIS:            Map, Site Geometries, Circuit Routes
Tools:          Route Finder, Neighbors
```

- [ ] **Step 2: Verify menu renders**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 3: Commit**

```
feat(nav): add Cable Routing menu group with segments, slack loops, pull sheets
```

---

## Task 7: Route Validation

**Files:**
- Create: `netbox_pathways/routing.py`
- Test: `tests/test_routing.py` (create)

- [ ] **Step 1: Write failing tests for route validation**

Create `tests/test_routing.py`:

```python
import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure
from netbox_pathways.routing import validate_cable_route


@pytest.mark.django_db
class TestValidateCableRoute:
    @pytest.fixture
    def structures(self):
        return [Structure.objects.create(name=f"MH-R-{i}") for i in range(4)]

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-R-001")

    def _make_conduit(self, name, s_from, s_to):
        srid = get_srid()
        return Conduit.objects.create(
            name=name, start_structure=s_from, end_structure=s_to,
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    def test_no_segments(self, cable):
        result = validate_cable_route(cable.pk)
        assert result['segment_count'] == 0
        assert result['valid'] is False

    def test_single_segment_valid(self, cable, structures):
        pw = self._make_conduit("C-R-1", structures[0], structures[1])
        CableSegment.objects.create(cable=cable, pathway=pw)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is True
        assert result['gaps'] == []

    def test_connected_route_valid(self, cable, structures):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1])
        pw2 = self._make_conduit("C-R-2", structures[1], structures[2])
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is True
        assert result['gaps'] == []

    def test_gap_detected(self, cable, structures):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1])
        pw2 = self._make_conduit("C-R-2", structures[2], structures[3])
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is False
        assert len(result['gaps']) == 1

    def test_segment_with_null_pathway(self, cable, structures):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1])
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=None)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is False
        assert len(result['gaps']) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_routing.py -v`
Expected: ImportError — `routing` module doesn't exist yet

- [ ] **Step 3: Implement validate_cable_route**

Create `netbox_pathways/routing.py`:

```python
"""
Cable route validation.

Checks whether a cable's route (sequence of CableSegments) is physically
connected — each consecutive pair of pathways must share a common endpoint
(Structure, Location, or ConduitJunction).
"""

from django.db.models import OuterRef, Subquery

from . import models
from .graph import _endpoint_nodes


def validate_cable_route(cable_id):
    """
    Validate that a cable's route is physically connected.

    Returns dict with:
        valid: bool — True if route is complete (no gaps)
        segment_count: int
        gaps: list of gap dicts
    """
    # Annotate conduit junction endpoints via subquery (same pattern as graph.py)
    junction_qs = models.ConduitJunction.objects.filter(
        trunk_conduit=OuterRef('pathway__pk')
    )
    segments = list(
        models.CableSegment.objects
        .filter(cable_id=cable_id)
        .select_related(
            'pathway',
            'pathway__start_structure',
            'pathway__end_structure',
            'pathway__start_location',
            'pathway__end_location',
        )
        .annotate(
            _start_junction_id=Subquery(
                junction_qs.filter(facing='start').values('pk')[:1]
            ),
            _end_junction_id=Subquery(
                junction_qs.filter(facing='end').values('pk')[:1]
            ),
        )
        .order_by('sequence')
    )

    segment_count = len(segments)
    if segment_count == 0:
        return {'valid': False, 'segment_count': 0, 'gaps': []}

    if segment_count == 1:
        pw = segments[0].pathway
        if pw is None:
            return {
                'valid': False, 'segment_count': 1,
                'gaps': [_null_gap(segments[0], None)],
            }
        return {'valid': True, 'segment_count': 1, 'gaps': []}

    gaps = []
    for i in range(len(segments) - 1):
        cur = segments[i]
        nxt = segments[i + 1]

        if cur.pathway is None or nxt.pathway is None:
            gaps.append(_null_gap(cur, nxt))
            continue

        # Transfer junction annotations to pathway objects for _endpoint_nodes
        cur.pathway._start_junction_id = cur._start_junction_id
        cur.pathway._end_junction_id = cur._end_junction_id
        nxt.pathway._start_junction_id = nxt._start_junction_id
        nxt.pathway._end_junction_id = nxt._end_junction_id

        cur_start, cur_end = _endpoint_nodes(cur.pathway)
        nxt_start, nxt_end = _endpoint_nodes(nxt.pathway)

        cur_endpoints = {n for n in (cur_start, cur_end) if n}
        nxt_endpoints = {n for n in (nxt_start, nxt_end) if n}

        if not cur_endpoints & nxt_endpoints:
            gaps.append({
                'after_segment_id': cur.pk,
                'before_segment_id': nxt.pk,
                'after_pathway': str(cur.pathway),
                'before_pathway': str(nxt.pathway),
                'detail': (
                    f"No shared endpoint between "
                    f"'{cur.pathway.name}' and '{nxt.pathway.name}'"
                ),
            })

    return {
        'valid': len(gaps) == 0,
        'segment_count': segment_count,
        'gaps': gaps,
    }


def _null_gap(cur_seg, nxt_seg):
    return {
        'after_segment_id': cur_seg.pk,
        'before_segment_id': nxt_seg.pk if nxt_seg else None,
        'after_pathway': str(cur_seg.pathway) if cur_seg.pathway else None,
        'before_pathway': str(nxt_seg.pathway) if nxt_seg and nxt_seg.pathway else None,
        'detail': 'Segment has no pathway assigned',
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/test_routing.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```
feat(routing): add cable route validation — checks consecutive segments share endpoints
```

---

## Task 8: Template Extensions — Route Status + Slack Panels

**Files:**
- Modify: `netbox_pathways/template_content.py`

- [ ] **Step 1: Add route status panel on cable detail page**

In `template_content.py`, add a new `CableRouteStatusExtension` for `dcim.cable` that:
- Calls `validate_cable_route(obj.pk)` 
- Renders a panel showing segment count, status badge (Complete/N gaps/No segments), gap details
- Links to pull sheet if valid

- [ ] **Step 2: Add SlackLoop panels on Cable and Structure detail pages**

Add template extensions that show an `ObjectsTablePanel` of SlackLoop entries:
- On `dcim.cable` detail: all slack loops for that cable
- On `netbox_pathways.structure` detail: all slack loops at that structure

- [ ] **Step 3: Modify existing CableRouteMapExtension**

Update `CableRouteMapExtension` (line 299) to:
- Order segments by `sequence` instead of `pk`
- Remove references to `seg.sequence` in segment naming (already done)
- Add route status info to the map panel context

- [ ] **Step 4: Register new extensions in template_extensions list**

Add the new extensions to the `template_extensions` list at the bottom of the file.

- [ ] **Step 5: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 6: Commit**

```
feat(templates): add route status panel and slack loop panels on cable/structure detail
```

---

## Task 9: Pull Sheet Gating

**Files:**
- Modify: `netbox_pathways/views.py:744-787`
- Modify: `netbox_pathways/templates/netbox_pathways/pullsheet_detail.html`

- [ ] **Step 1: Update PullSheetDetailView**

In `views.py`, update `PullSheetDetailView.get()`:
- Call `validate_cable_route(cable.pk)`
- If not valid, render an error template or message instead of the pull sheet
- Order segments by `sequence`
- Replace `total_slack` aggregation with a SlackLoop query: `SlackLoop.objects.filter(cable=cable).aggregate(total_slack=Sum('length'))`
- Pass slack loops to template context

- [ ] **Step 2: Update pull sheet template**

In `pullsheet_detail.html`:
- Remove the per-segment `slack_length` column from the route table
- Add a separate "Slack Loops" section below the route table showing SlackLoop entries grouped by structure
- Update the totals footer to use slack from SlackLoop

- [ ] **Step 3: Update PullSheetListView**

Add a route validity annotation or status column to help users identify which cables have complete routes.

- [ ] **Step 4: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 5: Commit**

```
feat(pullsheets): gate on valid route, show slack from SlackLoop model
```

---

## Task 10: Update graph.py and Final Cleanup

**Files:**
- Modify: `netbox_pathways/graph.py:206-242`
- Modify: `netbox_pathways/management/commands/generate_sample_data.py`

- [ ] **Step 1: Update trace_cable to order by sequence**

In `graph.py`, update `trace_cable()`:
- Change `.order_by('pk')` to `.order_by('sequence')`

- [ ] **Step 2: Update generate_sample_data**

In `generate_sample_data.py`, update CableSegment creation to not set `slack_length` (already done earlier). Add SlackLoop sample data generation.

- [ ] **Step 3: Run full test suite**

Run: `cd /opt/netbox/netbox && python -m pytest /opt/netbox-pathways/tests/ -v`
Expected: All PASS

- [ ] **Step 4: Run Django system check**

Run: `cd /opt/netbox/netbox && python manage.py check`
Expected: No issues

- [ ] **Step 5: Commit**

```
chore: update graph traversal ordering and sample data for cable routing redesign
```

---

## Task Summary

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1 | CableSegment model changes (sequence, remove slack) | None |
| 2 | SlackLoop model | Task 1 |
| 3 | CRUD layer (forms, tables, filters, search, panels) | Tasks 1-2 |
| 4 | API layer (serializers, viewsets, routes) | Tasks 1-3 |
| 5 | Views and URLs | Tasks 1-4 |
| 6 | Navigation reorganization | Task 5 |
| 7 | Route validation | Tasks 1-2 |
| 8 | Template extensions (route status, slack panels, map) | Tasks 5, 7 |
| 9 | Pull sheet gating | Tasks 7-8 |
| 10 | Graph.py update + final cleanup | Tasks 1-9 |
