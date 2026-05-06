from dcim.models import Cable, Site
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.object_actions import (
    AddObject,
    BulkDelete,
    BulkEdit,
    BulkExport,
    CloneObject,
    DeleteObject,
    EditObject,
    ObjectAction,
)
from netbox.ui import layout
from netbox.ui.panels import CommentsPanel, ObjectsTablePanel, TemplatePanel
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from netbox_pathways.registry import registry as map_layer_registry

from . import filterforms, filters, forms, models, tables
from .choices import PlannedRouteStatusChoices
from .graph import PathwayGraph, _endpoint_nodes, connected_pathways_db
from .ui import panels


def _map_url_for(obj):
    """Build a map URL that centres on and selects this object."""
    if hasattr(obj, "pathway_type") and obj.pathway_type:
        feature_type = obj.pathway_type
    else:
        feature_type = "structure"
    return reverse("plugins:netbox_pathways:map") + f"?select={feature_type}-{obj.pk}"


class ViewInMap(ObjectAction):
    label = "Map"
    template_name = "netbox_pathways/buttons/view_in_map.html"

    @classmethod
    def get_url(cls, obj):
        return _map_url_for(obj)


# --- Structure ---


class StructureListView(generic.ObjectListView):
    queryset = models.Structure.objects.select_related("site", "tenant")
    table = tables.StructureTable
    filterset = filters.StructureFilterSet
    filterset_form = filterforms.StructureFilterForm


class StructureView(generic.ObjectView):
    queryset = models.Structure.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.StructurePanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        right_panels=[],
        bottom_panels=[
            TemplatePanel(
                template_name="netbox_pathways/inc/connected_structures_panel.html",
            ),
        ],
    )

    def get_extra_context(self, request, instance):
        # Find all structures directly connected via any pathway
        connected_ids = set()
        pathways = models.Pathway.objects.filter(
            Q(start_structure=instance) | Q(end_structure=instance)
        ).select_related("start_structure", "end_structure")
        for p in pathways:
            if p.start_structure_id and p.start_structure_id != instance.pk:
                connected_ids.add(p.start_structure_id)
            if p.end_structure_id and p.end_structure_id != instance.pk:
                connected_ids.add(p.end_structure_id)

        connected_qs = models.Structure.objects.filter(pk__in=connected_ids).select_related("site", "tenant")
        table = tables.StructureTable(connected_qs, orderable=False)
        table.columns.hide("actions")
        table.columns.hide("pk")

        return {
            "connected_structures_table": table,
        }


class StructureEditView(generic.ObjectEditView):
    queryset = models.Structure.objects.all()
    form = forms.StructureForm


class StructureDeleteView(generic.ObjectDeleteView):
    queryset = models.Structure.objects.all()


class StructureBulkImportView(generic.BulkImportView):
    queryset = models.Structure.objects.all()
    model_form = forms.StructureImportForm


class StructureBulkEditView(generic.BulkEditView):
    queryset = models.Structure.objects.all()
    filterset = filters.StructureFilterSet
    table = tables.StructureTable
    form = forms.StructureBulkEditForm


class StructureBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Structure.objects.all()
    table = tables.StructureTable


class StructureCreateSiteView(LoginRequiredMixin, View):
    """Create a NetBox Site from a Structure and link them."""

    def post(self, request, pk):
        if not request.user.has_perm("dcim.add_site"):
            messages.error(request, "You do not have permission to create sites.")
            return redirect("plugins:netbox_pathways:structure", pk=pk)

        structure = get_object_or_404(models.Structure, pk=pk)

        if structure.site:
            messages.warning(request, f"Structure already has a linked site: {structure.site}")
            return redirect(structure.get_absolute_url())

        # Generate a unique slug
        base_slug = slugify(structure.name)[:100]
        slug = base_slug
        counter = 2
        while Site.objects.filter(slug=slug).exists():
            suffix = f"-{counter}"
            slug = base_slug[: 100 - len(suffix)] + suffix
            counter += 1

        # Handle duplicate site names
        name = structure.name[:100]
        if Site.objects.filter(name=name).exists():
            messages.error(
                request,
                f'A site named "{name}" already exists. Create the site manually with a different name.',
            )
            return redirect(structure.get_absolute_url())

        site = Site.objects.create(
            name=name,
            slug=slug,
            status="active",
            tenant=structure.tenant,
        )
        structure.site = site
        structure.save()

        messages.success(request, f'Created site "{site.name}" and linked it to this structure.')
        edit_url = reverse("dcim:site_edit", args=[site.pk])
        return redirect(f"{edit_url}?return_url={structure.get_absolute_url()}")


@register_model_view(models.Structure, "conduit_banks")
class StructureConduitBanksView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.ConduitBank
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet
    tab = ViewTab(
        label="Conduit Banks",
        badge=lambda obj: models.ConduitBank.objects.filter(Q(start_structure=obj) | Q(end_structure=obj)).count(),
    )

    def get_children(self, request, parent):
        return models.ConduitBank.objects.filter(Q(start_structure=parent) | Q(end_structure=parent)).annotate(
            conduit_count=Count("conduits")
        )


@register_model_view(models.Structure, "conduits")
class StructureConduitsView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.Conduit
    table = tables.ConduitTable
    filterset = filters.ConduitFilterSet
    tab = ViewTab(
        label="Conduits",
        badge=lambda obj: models.Conduit.objects.filter(Q(start_structure=obj) | Q(end_structure=obj)).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.Conduit.objects.filter(Q(start_structure=parent) | Q(end_structure=parent)).annotate(
            cables_routed=Count("cable_segments"),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
        )


@register_model_view(models.Structure, "aerial_spans")
class StructureAerialSpansView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.AerialSpan
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet
    tab = ViewTab(
        label="Aerial Spans",
        badge=lambda obj: models.AerialSpan.objects.filter(Q(start_structure=obj) | Q(end_structure=obj)).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.AerialSpan.objects.filter(Q(start_structure=parent) | Q(end_structure=parent)).annotate(
            cables_routed=Count("cable_segments"),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
        )


@register_model_view(models.Structure, "direct_buried")
class StructureDirectBuriedView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.DirectBuried
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet
    tab = ViewTab(
        label="Direct Buried",
        badge=lambda obj: models.DirectBuried.objects.filter(Q(start_structure=obj) | Q(end_structure=obj)).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.DirectBuried.objects.filter(Q(start_structure=parent) | Q(end_structure=parent)).annotate(
            cables_routed=Count("cable_segments"),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
        )


# --- Pathway (base) ---


class PathwayListView(generic.ObjectListView):
    queryset = models.Pathway.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
    ).annotate(
        cables_routed=Count("cable_segments"),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
    )
    table = tables.PathwayTable
    filterset = filters.PathwayFilterSet
    filterset_form = filterforms.PathwayFilterForm
    actions = (BulkExport,)


class PathwayView(generic.ObjectView):
    queryset = models.Pathway.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.PathwayPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.PathwayLocation",
                title="Waypoints",
                filters={"pathway_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


# --- Conduit ---


class ConduitListView(generic.ObjectListView):
    queryset = models.Conduit.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "conduit_bank",
        "tenant",
    ).annotate(
        cables_routed=Count("cable_segments"),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
    )
    table = tables.ConduitTable
    filterset_form = filterforms.ConduitFilterForm
    filterset = filters.ConduitFilterSet


class ConduitView(generic.ObjectView):
    queryset = models.Conduit.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.Innerduct",
                title="Innerducts",
                filters={"parent_conduit_id": lambda ctx: ctx["object"].pk},
            ),
            ObjectsTablePanel(
                model="netbox_pathways.CableSegment",
                title="Cable Segments",
                filters={"pathway_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


class ConduitEditView(generic.ObjectEditView):
    queryset = models.Conduit.objects.all()
    form = forms.ConduitForm


class ConduitDeleteView(generic.ObjectDeleteView):
    queryset = models.Conduit.objects.all()


class ConduitBulkImportView(generic.BulkImportView):
    queryset = models.Conduit.objects.all()
    model_form = forms.ConduitImportForm


class ConduitBulkEditView(generic.BulkEditView):
    queryset = models.Conduit.objects.all()
    filterset = filters.ConduitFilterSet
    table = tables.ConduitTable
    form = forms.ConduitBulkEditForm


class ConduitBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Conduit.objects.all()
    table = tables.ConduitTable


@register_model_view(models.Conduit, "innerducts")
class ConduitInnerductsView(generic.ObjectChildrenView):
    queryset = models.Conduit.objects.all()
    child_model = models.Innerduct
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet
    tab = ViewTab(
        label="Innerducts",
        badge=lambda obj: obj.innerducts.count(),
    )

    def get_children(self, request, parent):
        return parent.innerducts.annotate(
            cables_routed=Count("cable_segments"),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
        )


# --- Aerial Span ---


class AerialSpanListView(generic.ObjectListView):
    queryset = models.AerialSpan.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
    ).annotate(
        cables_routed=Count("cable_segments"),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
    )
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet
    filterset_form = filterforms.AerialSpanFilterForm


class AerialSpanView(generic.ObjectView):
    queryset = models.AerialSpan.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.AerialSpanPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.CableSegment",
                title="Cable Segments",
                filters={"pathway_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


class AerialSpanEditView(generic.ObjectEditView):
    queryset = models.AerialSpan.objects.all()
    form = forms.AerialSpanForm


class AerialSpanDeleteView(generic.ObjectDeleteView):
    queryset = models.AerialSpan.objects.all()


class AerialSpanBulkImportView(generic.BulkImportView):
    queryset = models.AerialSpan.objects.all()
    model_form = forms.AerialSpanImportForm


class AerialSpanBulkEditView(generic.BulkEditView):
    queryset = models.AerialSpan.objects.all()
    filterset = filters.AerialSpanFilterSet
    table = tables.AerialSpanTable
    form = forms.AerialSpanBulkEditForm


class AerialSpanBulkDeleteView(generic.BulkDeleteView):
    queryset = models.AerialSpan.objects.all()
    table = tables.AerialSpanTable


# --- Direct Buried ---


class DirectBuriedListView(generic.ObjectListView):
    queryset = models.DirectBuried.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
    ).annotate(
        cables_routed=Count("cable_segments"),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
    )
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet
    filterset_form = filterforms.DirectBuriedFilterForm
    actions = (AddObject, BulkExport, BulkEdit, BulkDelete)


class DirectBuriedView(generic.ObjectView):
    queryset = models.DirectBuried.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.DirectBuriedPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.CableSegment",
                title="Cable Segments",
                filters={"pathway_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


class DirectBuriedEditView(generic.ObjectEditView):
    queryset = models.DirectBuried.objects.all()
    form = forms.DirectBuriedForm


class DirectBuriedDeleteView(generic.ObjectDeleteView):
    queryset = models.DirectBuried.objects.all()


class DirectBuriedBulkEditView(generic.BulkEditView):
    queryset = models.DirectBuried.objects.all()
    filterset = filters.DirectBuriedFilterSet
    table = tables.DirectBuriedTable
    form = forms.DirectBuriedBulkEditForm


class DirectBuriedBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DirectBuried.objects.all()
    table = tables.DirectBuriedTable


# --- Innerduct ---


class InnerductListView(generic.ObjectListView):
    queryset = models.Innerduct.objects.select_related("parent_conduit").annotate(
        cables_routed=Count("cable_segments"),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef("pk"))),
    )
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet
    filterset_form = filterforms.InnerductFilterForm
    actions = (AddObject, BulkExport, BulkEdit, BulkDelete)


class InnerductView(generic.ObjectView):
    queryset = models.Innerduct.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.InnerductPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.CableSegment",
                title="Cable Segments",
                filters={"pathway_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


class InnerductEditView(generic.ObjectEditView):
    queryset = models.Innerduct.objects.all()
    form = forms.InnerductForm


class InnerductDeleteView(generic.ObjectDeleteView):
    queryset = models.Innerduct.objects.all()


class InnerductBulkEditView(generic.BulkEditView):
    queryset = models.Innerduct.objects.all()
    filterset = filters.InnerductFilterSet
    table = tables.InnerductTable
    form = forms.InnerductBulkEditForm


class InnerductBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Innerduct.objects.all()
    table = tables.InnerductTable


# --- Conduit Bank ---


class ConduitBankListView(generic.ObjectListView):
    queryset = models.ConduitBank.objects.select_related("start_structure", "end_structure", "tenant").annotate(
        conduit_count=Count("conduits"),
    )
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet
    filterset_form = filterforms.ConduitBankFilterForm


class ConduitBankView(generic.ObjectView):
    queryset = models.ConduitBank.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitBankPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model="netbox_pathways.Conduit",
                title="Conduits",
                filters={"conduit_bank_id": lambda ctx: ctx["object"].pk},
            ),
        ],
    )


class ConduitBankEditView(generic.ObjectEditView):
    queryset = models.ConduitBank.objects.all()
    form = forms.ConduitBankForm


class ConduitBankDeleteView(generic.ObjectDeleteView):
    queryset = models.ConduitBank.objects.all()


class ConduitBankBulkImportView(generic.BulkImportView):
    queryset = models.ConduitBank.objects.all()
    model_form = forms.ConduitBankImportForm


class ConduitBankBulkEditView(generic.BulkEditView):
    queryset = models.ConduitBank.objects.annotate(conduit_count=Count("conduits"))
    filterset = filters.ConduitBankFilterSet
    table = tables.ConduitBankTable
    form = forms.ConduitBankBulkEditForm


class ConduitBankBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ConduitBank.objects.annotate(conduit_count=Count("conduits"))
    table = tables.ConduitBankTable


# --- Conduit Junction ---


class ConduitJunctionListView(generic.ObjectListView):
    queryset = models.ConduitJunction.objects.select_related(
        "trunk_conduit",
        "branch_conduit",
        "towards_structure",
    )
    table = tables.ConduitJunctionTable
    filterset = filters.ConduitJunctionFilterSet
    filterset_form = filterforms.ConduitJunctionFilterForm
    actions = (AddObject, BulkExport)


class ConduitJunctionView(generic.ObjectView):
    queryset = models.ConduitJunction.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitJunctionPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class ConduitJunctionEditView(generic.ObjectEditView):
    queryset = models.ConduitJunction.objects.all()
    form = forms.ConduitJunctionForm


class ConduitJunctionDeleteView(generic.ObjectDeleteView):
    queryset = models.ConduitJunction.objects.all()


# --- Cable Segment ---


class CableSegmentListView(generic.ObjectListView):
    queryset = models.CableSegment.objects.select_related("cable", "pathway")
    table = tables.CableSegmentTable
    filterset = filters.CableSegmentFilterSet
    filterset_form = filterforms.CableSegmentFilterForm


class CableSegmentView(generic.ObjectView):
    queryset = models.CableSegment.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.CableSegmentPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            panels.HideIfEmptyObjectsTablePanel(
                model="netbox_pathways.CableSegment",
                title="Lashed With",
                filters={"lashed_with_id": lambda ctx: ctx["object"].pk},
                empty_check=lambda ctx: ctx["object"].lashed_with.exists(),
            ),
        ],
    )

    def get_extra_context(self, request, instance):
        ctx = super().get_extra_context(request, instance)
        siblings = list(
            models.CableSegment.objects.filter(cable=instance.cable).select_related("pathway").order_by("sequence")
        )
        current_idx = next((i for i, s in enumerate(siblings) if s.pk == instance.pk), 0)
        ctx["prev_segment"] = siblings[current_idx - 1] if current_idx > 0 else None
        ctx["next_segment"] = siblings[current_idx + 1] if current_idx < len(siblings) - 1 else None
        ctx["segment_ordinal"] = current_idx + 1
        ctx["segment_total"] = len(siblings)
        return ctx


class CableSegmentEditView(generic.ObjectEditView):
    queryset = models.CableSegment.objects.all()
    form = forms.CableSegmentForm


class CableSegmentDeleteView(generic.ObjectDeleteView):
    queryset = models.CableSegment.objects.all()


class CableSegmentBulkImportView(generic.BulkImportView):
    queryset = models.CableSegment.objects.all()
    model_form = forms.CableSegmentImportForm


class CableSegmentBulkEditView(generic.BulkEditView):
    queryset = models.CableSegment.objects.all()
    filterset = filters.CableSegmentFilterSet
    table = tables.CableSegmentTable
    form = forms.CableSegmentBulkEditForm


class CableSegmentBulkDeleteView(generic.BulkDeleteView):
    queryset = models.CableSegment.objects.all()
    table = tables.CableSegmentTable


# --- Pathway Location ---


class PathwayLocationListView(generic.ObjectListView):
    queryset = models.PathwayLocation.objects.select_related("pathway", "site", "location")
    table = tables.PathwayLocationTable
    filterset = filters.PathwayLocationFilterSet
    filterset_form = filterforms.PathwayLocationFilterForm
    actions = (AddObject, BulkExport)


class PathwayLocationView(generic.ObjectView):
    queryset = models.PathwayLocation.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.PathwayLocationPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class PathwayLocationEditView(generic.ObjectEditView):
    queryset = models.PathwayLocation.objects.all()
    form = forms.PathwayLocationForm


class PathwayLocationDeleteView(generic.ObjectDeleteView):
    queryset = models.PathwayLocation.objects.all()


# --- Site Geometry ---


class SiteGeometryListView(generic.ObjectListView):
    queryset = models.SiteGeometry.objects.select_related("site", "structure")
    table = tables.SiteGeometryTable
    filterset = filters.SiteGeometryFilterSet
    filterset_form = filterforms.SiteGeometryFilterForm
    actions = (AddObject, BulkExport)


class SiteGeometryView(generic.ObjectView):
    queryset = models.SiteGeometry.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.SiteGeometryPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class SiteGeometryEditView(generic.ObjectEditView):
    queryset = models.SiteGeometry.objects.all()
    form = forms.SiteGeometryForm


class SiteGeometryDeleteView(generic.ObjectDeleteView):
    queryset = models.SiteGeometry.objects.all()


# --- Circuit Geometry ---


class CircuitGeometryListView(generic.ObjectListView):
    queryset = models.CircuitGeometry.objects.select_related(
        "circuit",
        "circuit__provider",
    )
    table = tables.CircuitGeometryTable
    filterset = filters.CircuitGeometryFilterSet
    filterset_form = filterforms.CircuitGeometryFilterForm
    actions = (AddObject, BulkExport)


class CircuitGeometryView(generic.ObjectView):
    queryset = models.CircuitGeometry.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.CircuitGeometryPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class CircuitGeometryEditView(generic.ObjectEditView):
    queryset = models.CircuitGeometry.objects.all()
    form = forms.CircuitGeometryForm


class CircuitGeometryDeleteView(generic.ObjectDeleteView):
    queryset = models.CircuitGeometry.objects.all()


# --- Planned Route ---


class PlannedRouteListView(generic.ObjectListView):
    queryset = models.PlannedRoute.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
        "cable",
    )
    table = tables.PlannedRouteTable
    filterset = filters.PlannedRouteFilterSet
    filterset_form = filterforms.PlannedRouteFilterForm
    actions = (AddObject, BulkExport, BulkEdit, BulkDelete)


class SplitRoute(ObjectAction):
    label = "Split"
    template_name = "netbox_pathways/buttons/split_route.html"

    @classmethod
    def get_url(cls, obj):
        return reverse("plugins:netbox_pathways:plannedroute_split", args=[obj.pk])


class ReplanRoute(ObjectAction):
    label = "Re-plan"
    template_name = "netbox_pathways/buttons/replan_route.html"

    @classmethod
    def get_url(cls, obj):
        params = []
        if obj.start_structure_id:
            params.append(f"start={obj.start_structure_id}")
        if obj.end_structure_id:
            params.append(f"end={obj.end_structure_id}")
        qs = "&".join(params)
        base = reverse("plugins:netbox_pathways:route_planner")
        return f"{base}?{qs}" if qs else base


class RevertSplit(ObjectAction):
    label = "Revert Split"
    template_name = "netbox_pathways/buttons/revert_split.html"

    @classmethod
    def get_url(cls, obj):
        return reverse("plugins:netbox_pathways:plannedroute_revert", args=[obj.pk])


class ApplyRouteToCable(ObjectAction):
    label = "Apply to Cable"
    template_name = "netbox_pathways/buttons/apply_route.html"

    @classmethod
    def get_url(cls, obj):
        return reverse("plugins:netbox_pathways:plannedroute_apply", args=[obj.pk])


class PlannedRouteView(generic.ObjectView):
    queryset = models.PlannedRoute.objects.all()
    actions = (
        ReplanRoute,
        SplitRoute,
        RevertSplit,
        ApplyRouteToCable,
        CloneObject,
        EditObject,
        DeleteObject,
    )
    layout = layout.SimpleLayout(
        left_panels=[
            panels.PlannedRoutePanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        right_panels=[
            TemplatePanel("netbox_pathways/inc/plannedroute_map_panel.html"),
        ],
    )

    def get_extra_context(self, request, instance):
        import json

        from .geo import linestring_to_coords, point_to_latlon

        ctx = super().get_extra_context(request, instance)

        if instance.pathway_ids:
            pathways = models.Pathway.objects.filter(
                pk__in=instance.pathway_ids,
            ).select_related("start_structure", "end_structure")
            pw_map = {pw.pk: pw for pw in pathways}
            ordered = [pw_map[pid] for pid in instance.pathway_ids if pid in pw_map]
            ctx["pathways"] = ordered

            # Build route geometry for map rendering
            route_geometry = {"pathways": [], "structures": []}
            structure_pks = set()
            for pw in ordered:
                coords = linestring_to_coords(pw.path) if pw.path else []
                route_geometry["pathways"].append(
                    {
                        "pk": pw.pk,
                        "label": str(pw),
                        "pathway_type": pw.pathway_type or "",
                        "coords": coords,
                    }
                )
                if pw.start_structure_id:
                    structure_pks.add(pw.start_structure_id)
                if pw.end_structure_id:
                    structure_pks.add(pw.end_structure_id)

            structures = models.Structure.objects.filter(
                pk__in=structure_pks,
            ).only("pk", "name", "structure_type", "location")
            for s in structures:
                geo = point_to_latlon(s.location)
                if geo:
                    route_geometry["structures"].append(
                        {
                            "pk": s.pk,
                            "label": str(s),
                            "structure_type": s.structure_type or "",
                            "geo": geo,
                            "is_start": s.pk == instance.start_structure_id,
                            "is_end": s.pk == instance.end_structure_id,
                        }
                    )

            ctx["route_geometry_json"] = json.dumps(route_geometry)
        else:
            ctx["pathways"] = []
            ctx["route_geometry_json"] = ""

        # Lineage: children of this route (if split)
        ctx["children"] = instance.children.all() if instance.status == PlannedRouteStatusChoices.STATUS_SPLIT else []

        return ctx


class PlannedRouteEditView(generic.ObjectEditView):
    queryset = models.PlannedRoute.objects.all()
    form = forms.PlannedRouteForm


class PlannedRouteDeleteView(generic.ObjectDeleteView):
    queryset = models.PlannedRoute.objects.all()


class PlannedRouteBulkEditView(generic.BulkEditView):
    queryset = models.PlannedRoute.objects.all()
    filterset = filters.PlannedRouteFilterSet
    table = tables.PlannedRouteTable
    form = forms.PlannedRouteBulkEditForm


class PlannedRouteBulkDeleteView(generic.BulkDeleteView):
    queryset = models.PlannedRoute.objects.all()
    table = tables.PlannedRouteTable


class PlannedRouteSplitView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Split a planned route at a mid-route structure into two routes."""

    permission_required = "netbox_pathways.add_plannedroute"

    def get(self, request, pk):
        route = get_object_or_404(models.PlannedRoute, pk=pk)
        pathways = models.Pathway.objects.filter(
            pk__in=route.pathway_ids,
        ).select_related("start_structure", "end_structure")
        pw_map = {pw.pk: pw for pw in pathways}

        mid_structures = set()
        for pw in pathways:
            if pw.start_structure and pw.start_structure != route.start_structure:
                mid_structures.add(pw.start_structure)
            if pw.end_structure and pw.end_structure != route.end_structure:
                mid_structures.add(pw.end_structure)
        mid_structures.discard(route.end_structure)

        # Compute hop counts for each split option
        split_options = []
        for s in sorted(mid_structures, key=lambda s: str(s)):
            first_count = 0
            past_split = False
            for pid in route.pathway_ids:
                pw = pw_map.get(pid)
                if not pw:
                    continue
                if not past_split:
                    first_count += 1
                    if s in (pw.end_structure, pw.start_structure):
                        past_split = True
            second_count = len(route.pathway_ids) - first_count
            split_options.append(
                {
                    "pk": s.pk,
                    "label": str(s),
                    "first_hops": first_count,
                    "second_hops": second_count,
                }
            )

        return render(
            request,
            "netbox_pathways/plannedroute_split.html",
            {
                "route": route,
                "split_options": split_options,
            },
        )

    def post(self, request, pk):
        route = get_object_or_404(models.PlannedRoute, pk=pk)
        split_structure_pk = int(request.POST.get("split_structure"))
        name_first = request.POST.get("name_first", f"{route.name} (part 1)")
        name_second = request.POST.get("name_second", f"{route.name} (part 2)")

        split_structure = get_object_or_404(models.Structure, pk=split_structure_pk)

        pathways = models.Pathway.objects.filter(
            pk__in=route.pathway_ids,
        ).select_related("start_structure", "end_structure")
        pw_map = {pw.pk: pw for pw in pathways}

        first_ids = []
        second_ids = []
        past_split = False
        for pid in route.pathway_ids:
            pw = pw_map.get(pid)
            if not pw:
                continue
            if not past_split:
                first_ids.append(pid)
                if split_structure in (pw.end_structure, pw.start_structure):
                    past_split = True
            else:
                second_ids.append(pid)

        models.PlannedRoute.objects.create(
            name=name_first,
            start_structure=route.start_structure,
            start_location=route.start_location,
            end_structure=split_structure,
            pathway_ids=first_ids,
            tenant=route.tenant,
            parent=route,
        )
        models.PlannedRoute.objects.create(
            name=name_second,
            start_structure=split_structure,
            end_structure=route.end_structure,
            end_location=route.end_location,
            pathway_ids=second_ids,
            tenant=route.tenant,
            parent=route,
        )

        route.status = PlannedRouteStatusChoices.STATUS_SPLIT
        route.save()

        messages.success(request, f'Route split into "{name_first}" and "{name_second}".')
        return redirect("plugins:netbox_pathways:plannedroute_list")


class PlannedRouteRevertSplitView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Revert a split: restore parent to draft, delete children."""

    permission_required = (
        "netbox_pathways.change_plannedroute",
        "netbox_pathways.delete_plannedroute",
    )

    def post(self, request, pk):
        route = get_object_or_404(models.PlannedRoute, pk=pk)
        if route.status != PlannedRouteStatusChoices.STATUS_SPLIT:
            messages.error(request, "Only split routes can be reverted.")
            return redirect(route.get_absolute_url())

        child_count = route.children.count()
        route.children.all().delete()
        route.status = PlannedRouteStatusChoices.STATUS_DRAFT
        route.save()

        messages.success(request, f"Split reverted — {child_count} child route(s) removed.")
        return redirect(route.get_absolute_url())


class PlannedRouteApplyView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Apply a planned route to a cable as CableSegments."""

    permission_required = (
        "netbox_pathways.change_plannedroute",
        "netbox_pathways.add_cablesegment",
    )

    def get(self, request, pk):
        route = get_object_or_404(models.PlannedRoute, pk=pk)

        pathways = models.Pathway.objects.filter(
            pk__in=route.pathway_ids,
        ).select_related("start_structure", "end_structure")
        pw_map = {pw.pk: pw for pw in pathways}
        pw_ordered = [pw_map[pid] for pid in route.pathway_ids if pid in pw_map]

        apply_form = forms.PlannedRouteApplyForm(
            initial={"cable": route.cable_id} if route.cable_id else None,
        )

        return render(
            request,
            "netbox_pathways/plannedroute_apply.html",
            {
                "route": route,
                "pathways": pw_ordered,
                "apply_form": apply_form,
            },
        )

    def post(self, request, pk):
        route = get_object_or_404(models.PlannedRoute, pk=pk)
        cable_pk = request.POST.get("cable")
        cable = get_object_or_404(Cable, pk=cable_pk)

        with transaction.atomic():
            models.CableSegment.objects.filter(cable=cable).delete()
            for i, pw_id in enumerate(route.pathway_ids, start=1):
                seg = models.CableSegment(cable=cable, pathway_id=pw_id, sequence=i)
                seg.save()

            route.cable = cable
            route.status = "assigned"
            route.save()

        messages.success(request, f"Route applied to cable {cable}.")
        return redirect(f"/dcim/cables/{cable.pk}/")


# --- Route Planner ---


class RoutePlannerView(LoginRequiredMixin, View):
    """Route planner page with map + sidebar constraint builder."""

    def get(self, request):
        import json

        from django.conf import settings

        cable_pk = request.GET.get("cable")
        cable = None
        initial = {}

        start_structure = None
        end_structure = None

        if cable_pk:
            cable = get_object_or_404(Cable, pk=cable_pk)

        # Explicit start/end query params take priority (e.g. gap planning)
        start_pk = request.GET.get("start")
        end_pk = request.GET.get("end")
        if start_pk:
            start_structure = models.Structure.objects.filter(pk=start_pk).first()
            if start_structure:
                initial["start_structure"] = start_structure.pk
        if end_pk:
            end_structure = models.Structure.objects.filter(pk=end_pk).first()
            if end_structure:
                initial["end_structure"] = end_structure.pk

        # Fall back to cable terminations if not explicitly provided
        if cable and not start_structure:
            start_structure = self._resolve_termination(cable, "A")
            if start_structure:
                initial["start_structure"] = start_structure.pk
        if cable and not end_structure:
            end_structure = self._resolve_termination(cable, "B")
            if end_structure:
                initial["end_structure"] = end_structure.pk

        form = forms.RoutePlannerEndpointForm(initial=initial)

        # Build tile / map config (same pattern as MapView)
        plugin_cfg = settings.PLUGINS_CONFIG.get("netbox_pathways", {})

        from . import NetBoxPathwaysConfig

        map_config = NetBoxPathwaysConfig._map_config or {}

        pathways_config = {
            "apiBase": "/api/plugins/pathways/geo/",
            "baseLayers": map_config.get("baseLayers", []),
            "maxZoom": map_config.get("maxZoom", 22),
            "minZoom": map_config.get("minZoom", 1),
        }

        # Compute data extent for initial bounds
        extent = MapView._data_extent(MapView())
        default_lat = plugin_cfg.get("map_center_lat", 45.5017)
        default_lon = plugin_cfg.get("map_center_lon", -73.5673)
        default_zoom = plugin_cfg.get("map_zoom", 10)

        ctx = {
            "form": form,
            "cable": cable,
            "start_structure": start_structure,
            "end_structure": end_structure,
            "pathways_config_json": json.dumps(pathways_config),
        }

        if extent:
            ctx["map_center_lat"] = (extent[1] + extent[3]) / 2
            ctx["map_center_lon"] = (extent[0] + extent[2]) / 2
            ctx["map_zoom"] = default_zoom
            ctx["map_bounds"] = json.dumps(
                [
                    [extent[1], extent[0]],
                    [extent[3], extent[2]],
                ]
            )
        else:
            ctx["map_center_lat"] = default_lat
            ctx["map_center_lon"] = default_lon
            ctx["map_zoom"] = default_zoom
            ctx["map_bounds"] = ""

        return render(request, "netbox_pathways/route_planner.html", ctx)

    def _resolve_termination(self, cable, end):
        from dcim.models import CableTermination

        term = CableTermination.objects.filter(cable=cable, cable_end=end).first()
        if not term or not term._site_id:
            return None
        structures = models.Structure.objects.filter(site_id=term._site_id)
        return structures.first()


class RoutePlannerFindView(LoginRequiredMixin, View):
    """HTMX: Run constraint-based route finding."""

    @staticmethod
    def _parse_int_list(raw):
        """Parse a comma-separated or multi-value list of integer PKs."""
        if not raw:
            return None
        if isinstance(raw, list):
            items = []
            for item in raw:
                for part in str(item).split(","):
                    part = part.strip()
                    if part:
                        try:
                            items.append(int(part))
                        except (ValueError, TypeError):
                            pass
            return items or None
        parts = [p.strip() for p in str(raw).split(",") if p.strip()]
        try:
            return [int(p) for p in parts] or None
        except (ValueError, TypeError):
            return None

    def post(self, request):
        import json

        from .geo import linestring_to_coords, point_to_latlon
        from .route_engine import find_route

        start_pk = request.POST.get("start_structure")
        end_pk = request.POST.get("end_structure")
        if not start_pk or not end_pk:
            return HttpResponse(
                '<div class="pw-results-empty" style="padding:20px 14px;">'
                '<p class="mb-0">Select both start and end structures.</p></div>',
            )

        # Parse constraints from form
        avoid_pathway_types = request.POST.getlist("avoid_pathway_types") or None
        avoid_structure_types = request.POST.getlist("avoid_structure_types") or None
        avoid_structures = self._parse_int_list(request.POST.getlist("avoid_structures"))
        avoid_cables = self._parse_int_list(request.POST.getlist("avoid_cables"))
        avoid_circuits = self._parse_int_list(request.POST.getlist("avoid_circuits"))
        avoid_circuit_geometries = self._parse_int_list(
            request.POST.getlist("avoid_circuit_geometries"),
        )
        avoid_tenants = self._parse_int_list(request.POST.getlist("avoid_tenants"))
        must_pass_through = self._parse_int_list(request.POST.getlist("must_pass_through"))

        prefer_in_use = int(request.POST.get("prefer_in_use", 0))
        include_inactive = request.POST.get("include_inactive") == "on"

        start_node = ("structure", int(start_pk))
        end_node = ("structure", int(end_pk))

        result = find_route(
            start_node=start_node,
            end_node=end_node,
            avoid_pathway_types=avoid_pathway_types,
            avoid_structure_types=avoid_structure_types,
            include_inactive=include_inactive,
            avoid_structures=avoid_structures,
            avoid_cables=avoid_cables,
            avoid_circuits=avoid_circuits,
            avoid_circuit_geometries=avoid_circuit_geometries,
            avoid_tenants=avoid_tenants,
            must_pass_through=must_pass_through,
            prefer_in_use_factor=prefer_in_use,
        )

        routes = []
        route_geometry = {"pathways": [], "start": None, "end": None}
        if result:
            cost, pathway_ids = result
            pathways = models.Pathway.objects.filter(
                pk__in=pathway_ids,
            ).select_related("start_structure", "end_structure")
            pw_map = {pw.pk: pw for pw in pathways}
            ordered = [pw_map[pid] for pid in pathway_ids if pid in pw_map]
            routes.append(
                {
                    "cost": cost,
                    "hop_count": len(pathway_ids),
                    "pathways": ordered,
                    "pathway_ids": ",".join(str(pid) for pid in pathway_ids),
                }
            )

            # Build route geometry for map rendering
            # Collect all structures along the route
            structure_pks = set()
            for pw in ordered:
                coords = linestring_to_coords(pw.path) if pw.path else []
                route_geometry["pathways"].append(
                    {
                        "pk": pw.pk,
                        "label": str(pw),
                        "type": pw.get_pathway_type_display() if pw.pathway_type else "",
                        "pathway_type": pw.pathway_type or "",
                        "coords": coords,
                    }
                )
                if pw.start_structure_id:
                    structure_pks.add(pw.start_structure_id)
                if pw.end_structure_id:
                    structure_pks.add(pw.end_structure_id)

            # Fetch all route structures for markers
            structures = models.Structure.objects.filter(
                pk__in=structure_pks,
            ).only("pk", "name", "structure_type", "location")
            route_structures = []
            for s in structures:
                geo = point_to_latlon(s.location)
                if geo:
                    is_start = s.pk == int(start_pk)
                    is_end = s.pk == int(end_pk)
                    route_structures.append(
                        {
                            "pk": s.pk,
                            "label": str(s),
                            "type": s.get_structure_type_display() if s.structure_type else "",
                            "structure_type": s.structure_type or "",
                            "geo": geo,
                            "role": "start" if is_start else ("end" if is_end else "mid"),
                        }
                    )
            route_geometry["structures"] = route_structures

            # Build interleaved hop list: structure → pathway → structure → ...
            # Each pathway has a fixed start/end in the DB, but the route may
            # traverse it in either direction.  Track the "current" node to
            # determine entry/exit for each pathway.
            struct_map = {s["pk"]: s for s in route_structures}
            hops = []
            seen_structures = set()
            current_pk = int(start_pk)
            for pw in ordered:
                # Determine traversal direction: does the route enter via
                # start_structure or end_structure?
                ss_pk = pw.start_structure_id
                es_pk = pw.end_structure_id
                if current_pk == es_pk:
                    entry_pk, exit_pk = es_pk, ss_pk
                else:
                    entry_pk, exit_pk = ss_pk, es_pk

                # Add entry structure if not already listed
                if entry_pk and entry_pk not in seen_structures and entry_pk in struct_map:
                    seen_structures.add(entry_pk)
                    hops.append({"kind": "structure", **struct_map[entry_pk]})

                # Add the pathway
                mid = linestring_to_coords(pw.path)
                pw_geo = None
                if mid:
                    mid_idx = len(mid) // 2
                    pw_geo = (mid[mid_idx][1], mid[mid_idx][0])  # lat, lon
                hops.append(
                    {
                        "kind": "pathway",
                        "pk": pw.pk,
                        "label": str(pw),
                        "type": pw.get_pathway_type_display() if pw.pathway_type else "",
                        "length": pw.length,
                        "geo": pw_geo,
                    }
                )

                # Add exit structure
                if exit_pk and exit_pk not in seen_structures and exit_pk in struct_map:
                    seen_structures.add(exit_pk)
                    hops.append({"kind": "structure", **struct_map[exit_pk]})

                # Advance current position
                if exit_pk:
                    current_pk = exit_pk
            routes[0]["hops"] = hops

        cable_pk = request.POST.get("cable_pk")
        existing_segment_count = 0
        if cable_pk:
            existing_segment_count = models.CableSegment.objects.filter(cable_id=cable_pk).count()

        html = render_to_string(
            "netbox_pathways/inc/planner_results.html",
            {
                "routes": routes,
                "cable_pk": cable_pk,
                "existing_segment_count": existing_segment_count,
                "start_structure_pk": start_pk,
                "end_structure_pk": end_pk,
                "route_geometry_json": json.dumps(route_geometry),
            },
            request=request,
        )
        return HttpResponse(html)


class RoutePlannerSaveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Save a found route as a PlannedRoute."""

    permission_required = "netbox_pathways.add_plannedroute"

    def post(self, request):
        pathway_ids_str = request.POST.get("pathway_ids", "")
        pathway_ids = [int(pid) for pid in pathway_ids_str.split(",") if pid.strip()]
        start_pk = request.POST.get("start_structure")
        end_pk = request.POST.get("end_structure")
        name = request.POST.get("name", "").strip() or "Unnamed Route"
        cable_pk = request.POST.get("cable_pk")

        route = models.PlannedRoute.objects.create(
            name=name,
            start_structure_id=int(start_pk) if start_pk else None,
            end_structure_id=int(end_pk) if end_pk else None,
            pathway_ids=pathway_ids,
            cable_id=int(cable_pk) if cable_pk else None,
        )
        return redirect(route.get_absolute_url())


class RoutePlannerConstraintView(LoginRequiredMixin, View):
    """HTMX: Return a constraint card HTML fragment for the route planner."""

    # Constraint type definitions: (type_key, group, label, kind, extra)
    # kind: 'model' (DynamicModelMultipleChoiceField) or 'enum' (checkboxes)
    CONSTRAINT_TYPES = {
        "must_pass_through": {
            "group": "include",
            "label": "Pass through structure(s)",
            "kind": "model",
            "model": "netbox_pathways.Structure",
        },
        "avoid_structures": {
            "group": "avoid",
            "label": "Avoid structure(s)",
            "kind": "model",
            "model": "netbox_pathways.Structure",
        },
        "avoid_cables": {
            "group": "avoid",
            "label": "Avoid cable(s)",
            "kind": "model",
            "model": "dcim.Cable",
        },
        "avoid_circuits": {
            "group": "avoid",
            "label": "Avoid circuit(s)",
            "kind": "model",
            "model": "circuits.Circuit",
        },
        "avoid_circuit_geometries": {
            "group": "avoid",
            "label": "Avoid circuit geometry(s)",
            "kind": "model",
            "model": "netbox_pathways.CircuitGeometry",
        },
        "avoid_pathway_types": {
            "group": "avoid",
            "label": "Avoid pathway type(s)",
            "kind": "enum",
            "choices_class": "PathwayTypeChoices",
        },
        "avoid_structure_types": {
            "group": "avoid",
            "label": "Avoid structure type(s)",
            "kind": "enum",
            "choices_class": "StructureTypeChoices",
        },
        "avoid_tenants": {
            "group": "avoid",
            "label": "Avoid tenant(s)",
            "kind": "model",
            "model": "tenancy.Tenant",
        },
    }

    MODEL_MAP = {
        "netbox_pathways.Structure": lambda: models.Structure.objects.all(),
        "dcim.Cable": lambda: Cable.objects.all(),
        "circuits.Circuit": lambda: __import__(
            "circuits.models",
            fromlist=["Circuit"],
        ).Circuit.objects.all(),
        "netbox_pathways.CircuitGeometry": lambda: models.CircuitGeometry.objects.all(),
        "tenancy.Tenant": lambda: __import__(
            "tenancy.models",
            fromlist=["Tenant"],
        ).Tenant.objects.all(),
    }

    def get(self, request):
        from django.utils.safestring import mark_safe
        from utilities.forms.fields import DynamicModelMultipleChoiceField

        constraint_type = request.GET.get("type", "")
        cfg = self.CONSTRAINT_TYPES.get(constraint_type)
        if not cfg:
            return HttpResponse("", status=400)

        ctx = {
            "constraint_type": constraint_type,
            "group": cfg["group"],
            "label": cfg["label"],
        }

        if cfg["kind"] == "enum":
            from . import choices as choice_module

            choices_cls = getattr(choice_module, cfg["choices_class"])
            ctx["choices"] = [c for c in choices_cls.CHOICES if c[0] != "conduit_bank"]
        elif cfg["kind"] == "model":
            qs_factory = self.MODEL_MAP.get(cfg["model"])
            if qs_factory:
                # Use .none() queryset — the APISelect widget fetches options
                # on-demand via the REST API.  Passing the full queryset would
                # cause Django to materialise every row as <option> tags,
                # consuming gigabytes of RAM on large datasets.
                qs = qs_factory().none()
                field = DynamicModelMultipleChoiceField(
                    queryset=qs,
                    required=False,
                )
                from utilities.views import get_action_url

                api_url = get_action_url(qs.model, action="list", rest_api=True)
                widget_html = field.widget.render(
                    name=constraint_type,
                    value=[],
                    attrs={
                        "id": f"id_{constraint_type}",
                        "class": "form-select api-select",
                        "data-url": api_url,
                    },
                )
                ctx["widget_html"] = mark_safe(widget_html)  # noqa: S308

        html = render_to_string(
            "netbox_pathways/inc/constraint_card.html",
            ctx,
            request=request,
        )
        return HttpResponse(html)


# --- Map View ---


class MapView(LoginRequiredMixin, View):
    """Full-page infrastructure map. Data is fetched client-side from GeoJSON API."""

    def _safe_float(self, value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _data_extent(self):
        """Compute WGS84 bounding box of all structures + pathways.

        Uses a two-pass approach for structures: first compute a rough
        centroid, then re-compute the extent excluding points that are
        far from the median (> 2 degrees), which filters GPS outliers.
        """
        from django.db import connection

        bbox = None

        with connection.cursor() as cursor:
            # Structures — trimmed extent to reject outliers
            cursor.execute("""
                WITH pts AS (
                    SELECT ST_Transform(location, 4326) AS geom
                    FROM netbox_pathways_structure
                    WHERE location IS NOT NULL
                ),
                med AS (
                    SELECT ST_Y(ST_Centroid(ST_Collect(geom))) AS lat,
                           ST_X(ST_Centroid(ST_Collect(geom))) AS lon
                    FROM pts
                ),
                trimmed AS (
                    SELECT pts.geom FROM pts, med
                    WHERE abs(ST_Y(pts.geom) - med.lat) < 2
                      AND abs(ST_X(pts.geom) - med.lon) < 2
                )
                SELECT ST_Extent(geom) FROM trimmed
            """)
            row = cursor.fetchone()
            if row and row[0]:
                # Parse BOX(xmin ymin,xmax ymax)
                bbox = self._parse_box(row[0])

            # Pathways
            cursor.execute("""
                SELECT ST_Extent(ST_Transform(path, 4326))
                FROM netbox_pathways_pathway
                WHERE path IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                pbox = self._parse_box(row[0])
                if pbox:
                    if bbox:
                        bbox = (
                            min(bbox[0], pbox[0]),
                            min(bbox[1], pbox[1]),
                            max(bbox[2], pbox[2]),
                            max(bbox[3], pbox[3]),
                        )
                    else:
                        bbox = pbox

        return bbox  # (west, south, east, north) or None

    @staticmethod
    def _parse_box(box_str):
        """Parse PostGIS BOX(xmin ymin,xmax ymax) to (west, south, east, north)."""
        try:
            coords = box_str.replace("BOX(", "").replace(")", "")
            min_part, max_part = coords.split(",")
            west, south = (float(v) for v in min_part.split())
            east, north = (float(v) for v in max_part.split())
            return (west, south, east, north)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _resolve_feature_extent(select_param):
        """Resolve WGS84 bounding box from a select param like 'structure-123'.

        Returns (west, south, east, north) or None.
        """
        from django.contrib.gis.db.models import Extent
        from django.contrib.gis.db.models.functions import Transform

        try:
            ftype, fid = select_param.rsplit("-", 1)
            fid = int(fid)
        except (ValueError, AttributeError):
            return None

        model_map = {
            "structure": (models.Structure, "location"),
            "conduit": (models.Conduit, "path"),
            "conduit_bank": (models.ConduitBank, "path"),
            "aerial": (models.AerialSpan, "path"),
            "direct_buried": (models.DirectBuried, "path"),
        }
        entry = model_map.get(ftype)
        if not entry:
            return None

        model_cls, geom_field = entry
        try:
            result = (
                model_cls.objects.filter(pk=fid)
                .annotate(
                    _geo=Transform(geom_field, 4326),
                )
                .aggregate(bbox=Extent("_geo"))
            )
            bbox = result.get("bbox")
            if bbox:
                return bbox  # (west, south, east, north)
        except Exception:  # noqa: S110
            pass
        return None

    def get(self, request):
        import json

        from django.conf import settings

        plugin_cfg = settings.PLUGINS_CONFIG.get("netbox_pathways", {})

        api_base = reverse("plugins-api:netbox_pathways-api:api-root")
        geo_base = f"{api_base}geo/"

        pathways_config = {
            "maxNativeZoom": plugin_cfg.get("map_max_native_zoom", 19),
            "apiBase": geo_base,
            "overlays": plugin_cfg.get("map_overlays", []),
            "baseLayers": plugin_cfg.get("map_base_layers", []),
            "externalLayers": [layer.to_json(api_base=geo_base) for layer in map_layer_registry.all()],
        }

        # Compute extent from data; fall back to config or defaults
        extent = self._data_extent()
        default_lat = plugin_cfg.get("map_center_lat", 45.5017)
        default_lon = plugin_cfg.get("map_center_lon", -73.5673)
        default_zoom = plugin_cfg.get("map_zoom", 10)

        ctx = {
            "pathways_config_json": json.dumps(pathways_config),
        }

        ctx["kiosk"] = request.GET.get("kiosk", "").lower() == "true"
        ctx["selected_feature"] = request.GET.get("select", "")

        if request.GET.get("lat") or request.GET.get("lon"):
            ctx["map_center_lat"] = self._safe_float(request.GET.get("lat"), default_lat)
            ctx["map_center_lon"] = self._safe_float(request.GET.get("lon"), default_lon)
            ctx["map_zoom"] = self._safe_int(request.GET.get("zoom"), default_zoom)
            ctx["map_bounds"] = ""
        elif ctx["selected_feature"]:
            # Resolve bounds from the selected feature's geometry
            sel_ext = self._resolve_feature_extent(ctx["selected_feature"])
            if sel_ext:
                ctx["map_center_lat"] = (sel_ext[1] + sel_ext[3]) / 2
                ctx["map_center_lon"] = (sel_ext[0] + sel_ext[2]) / 2
                ctx["map_zoom"] = 18  # fallback if fitBounds not used
                ctx["map_bounds"] = json.dumps(
                    [
                        [sel_ext[1], sel_ext[0]],
                        [sel_ext[3], sel_ext[2]],
                    ]
                )
            elif extent:
                ctx["map_center_lat"] = (extent[1] + extent[3]) / 2
                ctx["map_center_lon"] = (extent[0] + extent[2]) / 2
                ctx["map_zoom"] = default_zoom
                ctx["map_bounds"] = json.dumps(
                    [
                        [extent[1], extent[0]],
                        [extent[3], extent[2]],
                    ]
                )
            else:
                ctx["map_center_lat"] = default_lat
                ctx["map_center_lon"] = default_lon
                ctx["map_zoom"] = default_zoom
                ctx["map_bounds"] = ""
        elif extent:
            ctx["map_center_lat"] = (extent[1] + extent[3]) / 2
            ctx["map_center_lon"] = (extent[0] + extent[2]) / 2
            ctx["map_zoom"] = default_zoom
            ctx["map_bounds"] = json.dumps(
                [
                    [extent[1], extent[0]],
                    [extent[3], extent[2]],
                ]
            )
        else:
            ctx["map_center_lat"] = default_lat
            ctx["map_center_lon"] = default_lon
            ctx["map_zoom"] = default_zoom
            ctx["map_bounds"] = ""

        return render(request, "netbox_pathways/map.html", ctx)


# --- Pull Sheet ---


class PullSheetListView(generic.ObjectListView):
    """Lists cables that have pathway segments routed, for pull sheet selection."""

    queryset = (
        Cable.objects.filter(
            pathway_segments__isnull=False,
        )
        .distinct()
        .annotate(
            segment_count=Count("pathway_segments"),
        )
    )
    table = tables.PullSheetCableTable
    template_name = "netbox_pathways/pullsheet_list.html"

    def get_extra_context(self, request):
        return {"title": "Pull Sheets"}


class PullSheetDetailView(LoginRequiredMixin, View):
    """Renders a pull sheet for a specific cable."""

    def get(self, request, cable_pk):
        from .routing import validate_cable_route

        cable = get_object_or_404(Cable, pk=cable_pk)
        route = validate_cable_route(cable.pk)

        segments = (
            models.CableSegment.objects.filter(cable=cable)
            .select_related(
                "pathway",
                "pathway__start_structure",
                "pathway__end_structure",
                "pathway__start_location",
                "pathway__end_location",
            )
            .order_by("sequence")
        )

        totals = segments.aggregate(
            total_pathway_length=Sum("pathway__length"),
        )

        return render(
            request,
            "netbox_pathways/pullsheet_detail.html",
            {
                "cable": cable,
                "segments": segments,
                "segment_count": segments.count(),
                "total_pathway_length": totals["total_pathway_length"] or 0,
                "route": route,
            },
        )


class AdjacencyView(LoginRequiredMixin, View):
    """Return pathways connected to a given node as JSON."""

    def get(self, request):
        node_type = request.GET.get("node_type")
        node_id = request.GET.get("node_id")
        if not node_type or not node_id:
            return JsonResponse(
                {"error": "node_type and node_id are required"},
                status=400,
            )
        try:
            node_id = int(node_id)
        except (ValueError, TypeError):
            return JsonResponse({"error": "node_id must be an integer"}, status=400)

        node = (node_type, node_id)
        pathways = connected_pathways_db(node)

        results = []
        for pw in pathways:
            dest = pw.end_endpoint or pw.start_endpoint
            results.append(
                {
                    "pathway_id": pw.pk,
                    "label": str(pw),
                    "destination": str(dest) if dest else "",
                    "length": pw.length or 0,
                    "pathway_type": pw.pathway_type,
                }
            )

        return JsonResponse(results, safe=False)


# --- Cable Routing Tab (on dcim.Cable detail page) ---


def _annotate_segments(segments):
    """Add display attributes to a list of CableSegment instances.

    Determines traversal direction for each segment so that gap rows link
    to the correct start/end structures in the route planner.
    """
    if not segments:
        return

    # First pass: determine traversal direction by finding shared structures
    # between consecutive connected segments.
    current_pk = None
    for i, seg in enumerate(segments):
        seg.ordinal = i + 1
        seg.gap_before = i > 0 and seg.sequence != segments[i - 1].sequence + 1
        seg.prev_sequence = segments[i - 1].sequence if i > 0 else 0

        pw = seg.pathway
        if not pw:
            seg.start_name = None
            seg.end_name = None
            continue

        ss = pw.start_structure_id
        es = pw.end_structure_id

        if current_pk is None and i == 0:
            # Determine first segment's entry from the next connected segment.
            # The shared structure between seg 0 and seg 1 is seg 0's EXIT,
            # so the entry is the opposite end.
            for j in range(1, len(segments)):
                if segments[j].sequence != segments[j - 1].sequence + 1:
                    break  # gap — can't determine from disconnected segment
                npw = segments[j].pathway
                if npw:
                    shared = {ss, es} & {npw.start_structure_id, npw.end_structure_id}
                    if shared:
                        exit_pk = shared.pop()
                        # Entry is the opposite end from exit
                        current_pk = es if exit_pk == ss else ss
                        break
            if current_pk is None:
                current_pk = ss  # fallback

        # After a gap, re-determine direction from the next connected segment
        if seg.gap_before and current_pk not in (ss, es):
            current_pk = None
            for j in range(i + 1, len(segments)):
                if segments[j].sequence != segments[j - 1].sequence + 1:
                    break
                npw = segments[j].pathway
                if npw:
                    shared = {ss, es} & {npw.start_structure_id, npw.end_structure_id}
                    if shared:
                        exit_pk = shared.pop()
                        current_pk = es if exit_pk == ss else ss
                        break
            if current_pk is None:
                current_pk = ss  # fallback

        # Determine entry/exit based on current position
        if current_pk == es:
            seg._entry_pk, seg._exit_pk = es, ss
        else:
            seg._entry_pk, seg._exit_pk = ss, es

        seg.start_name = str(pw.start_endpoint) if pw.start_endpoint else None
        seg.end_name = str(pw.end_endpoint) if pw.end_endpoint else None

        # Gap endpoint PKs for "Plan Route" link
        if seg.gap_before and i > 0:
            seg.gap_start_pk = segments[i - 1]._exit_pk if hasattr(segments[i - 1], "_exit_pk") else None
            seg.gap_end_pk = seg._entry_pk
        current_pk = seg._exit_pk


@register_model_view(Cable, "route", path="route")
class CableRouteView(generic.ObjectView):
    queryset = Cable.objects.all()
    template_name = "netbox_pathways/cable_route_tab.html"
    tab = ViewTab(
        label="Route",
        badge=lambda obj: obj.pathway_segments.count() or None,
    )

    def get_extra_context(self, request, instance):
        from .routing import validate_cable_route

        segments_qs = (
            models.CableSegment.objects.filter(cable=instance)
            .select_related(
                "pathway",
                "pathway__start_structure",
                "pathway__end_structure",
                "pathway__start_location",
                "pathway__end_location",
            )
            .order_by("sequence")
        )
        segments = list(segments_qs)

        _annotate_segments(segments)

        route = validate_cable_route(instance.pk)
        total_length = sum(s.pathway.length or 0 for s in segments if s.pathway)

        # Check routability
        from dcim.models import CableTermination

        a_exists = CableTermination.objects.filter(cable=instance, cable_end="A").exists()
        b_exists = CableTermination.objects.filter(cable=instance, cable_end="B").exists()

        return {
            "cable": instance,
            "segments": segments,
            "segment_count": len(segments),
            "total_length": total_length,
            "route_valid": route["valid"],
            "gap_count": len(route["gaps"]),
            "routable": a_exists and b_exists,
        }


# --- Cable Routing Panel HTMX Views ---


class CableRoutingMixin:
    """Shared helpers for routing panel views."""

    def _start_node(self, cable):
        """Resolve A termination to a graph node."""
        from dcim.models import CableTermination

        term = (
            CableTermination.objects.filter(
                cable=cable,
                cable_end="A",
            )
            .select_related("_site")
            .first()
        )
        if not term or not term._site_id:
            return None
        structures = models.Structure.objects.filter(site_id=term._site_id)
        if structures.count() == 1:
            return ("structure", structures.first().pk)
        first = structures.first()
        return ("structure", first.pk) if first else None

    def _end_node(self, cable):
        """Resolve B termination to a graph node."""
        from dcim.models import CableTermination

        term = (
            CableTermination.objects.filter(
                cable=cable,
                cable_end="B",
            )
            .select_related("_site")
            .first()
        )
        if not term or not term._site_id:
            return None
        structures = models.Structure.objects.filter(site_id=term._site_id)
        if structures.count() == 1:
            return ("structure", structures.first().pk)
        first = structures.first()
        return ("structure", first.pk) if first else None

    def _far_end_node(self, pathway, coming_from_node=None):
        """Return the opposite end of a pathway from the entry node."""
        start, end = _endpoint_nodes(pathway)
        if coming_from_node and coming_from_node == end:
            return start
        return end

    def _render_table(self, request, cable):
        segments = list(
            models.CableSegment.objects.filter(cable=cable)
            .select_related(
                "pathway",
                "pathway__start_structure",
                "pathway__end_structure",
                "pathway__start_location",
                "pathway__end_location",
            )
            .order_by("sequence")
        )
        _annotate_segments(segments)

        html = render_to_string(
            "netbox_pathways/inc/cable_segment_table.html",
            {"cable": cable, "segments": segments},
            request=request,
        )
        return HttpResponse(html)


class CableRoutingAddSegmentView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Show add-segment form or process segment creation."""

    permission_required = "netbox_pathways.add_cablesegment"

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        after_sequence = request.GET.get("after_sequence")

        segments = list(models.CableSegment.objects.filter(cable=cable).select_related("pathway").order_by("sequence"))

        if after_sequence is not None:
            after_sequence = int(after_sequence)
            prev_seg = next((s for s in segments if s.sequence == after_sequence), None)
            if prev_seg and prev_seg.pathway:
                node = self._far_end_node(prev_seg.pathway)
            else:
                node = self._start_node(cable)
        elif segments:
            last = segments[-1]
            if last.pathway:
                node = self._far_end_node(last.pathway)
            else:
                node = self._start_node(cable)
        else:
            node = self._start_node(cable)

        pathways = connected_pathways_db(node) if node else models.Pathway.objects.none()

        choices = []
        for pw in pathways:
            dest = pw.end_endpoint or pw.start_endpoint
            length_str = f"{pw.length:.1f}m" if pw.length else "?"
            choices.append((pw.pk, f"{pw} \u2192 {dest} ({length_str})"))

        html = render_to_string(
            "netbox_pathways/inc/cable_add_segment_form.html",
            {
                "cable": cable,
                "choices": choices,
                "after_sequence": after_sequence,
            },
            request=request,
        )
        return HttpResponse(html)

    def post(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        pathway_id = request.POST.get("pathway")
        after_sequence = request.POST.get("after_sequence")

        pathway = get_object_or_404(models.Pathway, pk=pathway_id) if pathway_id else None

        if after_sequence:
            sequence = int(after_sequence) + 1
            with transaction.atomic():
                models.CableSegment.objects.filter(
                    cable=cable,
                    sequence__gte=sequence,
                ).update(sequence=F("sequence") + 1)
                seg = models.CableSegment(cable=cable, pathway=pathway, sequence=sequence)
                seg.save()
        else:
            seg = models.CableSegment(cable=cable, pathway=pathway)
            seg.save()

        return self._render_table(request, cable)


class CableRoutingDeleteSegmentView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Delete a segment and return updated table."""

    permission_required = "netbox_pathways.delete_cablesegment"

    def post(self, request, cable_pk, segment_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        seg = get_object_or_404(models.CableSegment, pk=segment_pk, cable=cable)
        seg.delete()
        return self._render_table(request, cable)


class CableRoutingFindRouteView(CableRoutingMixin, LoginRequiredMixin, View):
    """HTMX: Find routes between cable A/B terminations."""

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        start_node = self._start_node(cable)
        end_node = self._end_node(cable)

        routes = []
        if start_node and end_node:
            graph = PathwayGraph.build_topology()
            result = graph.shortest_path(start_node, end_node)
            if result:
                routes = [result]

        enriched_routes = []
        for cost, pathway_ids in routes:
            pathways = models.Pathway.objects.filter(
                pk__in=pathway_ids,
            ).select_related("start_structure", "end_structure")
            pw_map = {pw.pk: pw for pw in pathways}
            enriched_routes.append(
                {
                    "cost": cost,
                    "hop_count": len(pathway_ids),
                    "pathways": [pw_map.get(pid) for pid in pathway_ids if pw_map.get(pid)],
                    "pathway_ids": ",".join(str(pid) for pid in pathway_ids),
                }
            )

        existing_count = models.CableSegment.objects.filter(cable=cable).count()

        html = render_to_string(
            "netbox_pathways/inc/cable_route_finder_results.html",
            {
                "cable": cable,
                "routes": enriched_routes,
                "existing_count": existing_count,
            },
            request=request,
        )
        return HttpResponse(html)


class CableRoutingApplyRouteView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Apply a found route -- create segments from pathway IDs."""

    permission_required = ("netbox_pathways.add_cablesegment", "netbox_pathways.delete_cablesegment")

    def post(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        pathway_ids_str = request.POST.get("pathway_ids", "")
        pathway_ids = [int(pid) for pid in pathway_ids_str.split(",") if pid.strip()]

        with transaction.atomic():
            models.CableSegment.objects.filter(cable=cable).delete()
            for i, pw_id in enumerate(pathway_ids, start=1):
                seg = models.CableSegment(cable=cable, pathway_id=pw_id, sequence=i)
                seg.save()

        return self._render_table(request, cable)


class CableRoutingTableView(CableRoutingMixin, LoginRequiredMixin, View):
    """HTMX: Re-render the segment table (used by Cancel button)."""

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        return self._render_table(request, cable)
