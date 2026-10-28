# Choice Fields

All choice fields use NetBox's `ChoiceSet` base class and allow blank values (field conditions are often unknown or undocumented in real-world cable plant data).

## StructureTypeChoices

| Value | Label | Color |
|-------|-------|-------|
| `pole` | Pole | Green |
| `manhole` | Manhole | Blue |
| `handhole` | Handhole | Cyan |
| `cabinet` | Cabinet | Orange |
| `vault` | Vault | Purple |
| `pedestal` | Pedestal | Yellow |
| `building_entrance` | Building Entrance | Red |
| `tower` | Tower | Dark Red |
| `roof` | Roof | Gray |
| `equipment_room` | Equipment Room | Teal |
| `telecom_closet` | Telecom Closet | Indigo |
| `riser_room` | Riser Room | Pink |

## PathwayStatusChoices

Same states as structures (see the Structures user guide). Applies to every pathway type. Default is `active`.

| Value | Label | Color |
|-------|-------|-------|
| `planned` | Planned | Cyan |
| `active` | Active | Green |
| `construction` | Under Construction | Blue |
| `decommissioning` | Decommissioning | Yellow |
| `retired` | Retired | Red |
| `abandoned` | Abandoned in place | Gray |

## PathwayTypeChoices

Required on every pathway. The type decides the type-specific fields, the
allowed parents and whether the map draws the pathway; see
[Pathways](../user-guide/pathways.md#hierarchy) for the containment rule.

| Value | Label | Color | Drawn on the map (top-level only) |
|-------|-------|-------|-----------------------------------|
| `conduit_bank` | Conduit Bank | Dark Brown | Yes |
| `conduit` | Conduit | Brown | Yes |
| `aerial` | Aerial Span | Blue | Yes |
| `direct_buried` | Direct Buried | Gray | Yes |
| `innerduct` | Innerduct | Orange | No |
| `tray` | Cable Tray | Green | No |
| `raceway` | Raceway | Cyan | No |
| `submarine` | Submarine | Navy | Yes |

The former `microduct` type is retired: a microduct is an innerduct
(distinguished by `size`), and a stand-alone microduct bundle is a direct
buried pathway with innerduct children.

## ConduitMaterialChoices

| Value | Label | Color |
|-------|-------|-------|
| `pvc` | PVC | White |
| `hdpe` | HDPE | Black |
| `steel` | Steel | Gray |
| `concrete` | Concrete | Gray |
| `fiberglass` | Fiberglass | Yellow |

## AerialTypeChoices

| Value | Label | Color |
|-------|-------|-------|
| `messenger` | Messenger | Black |
| `self_support` | Self-Supporting | Blue |
| `lashed` | Lashed | Green |
| `wrapped` | Wrapped | Orange |
| `adss` | ADSS | Purple |
| `opgw` | OPGW | Red |

## ConduitBankConfigChoices

| Value | Label | Color |
|-------|-------|-------|
| `1x2` | 1x2 | Blue |
| `1x3` | 1x3 | Green |
| `1x4` | 1x4 | Orange |
| `2x2` | 2x2 | Red |
| `2x3` | 2x3 | Purple |
| `3x3` | 3x3 | Brown |
| `3x4` | 3x4 | Navy |
| `custom` | Custom | Gray |

## EncasementTypeChoices

| Value | Label | Color |
|-------|-------|-------|
| `concrete` | Concrete | Gray |
| `direct_buried` | Direct Buried | Brown |
| `bore` | Bore | Blue |
| `bridge_attachment` | Bridge Attachment | Green |
| `tunnel` | Tunnel | Black |
