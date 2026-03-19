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
| `splice_closure` | Splice Closure | Brown |
| `tower` | Tower | Dark Red |
| `roof` | Roof | Gray |
| `equipment_room` | Equipment Room | Teal |
| `telecom_closet` | Telecom Closet | Indigo |
| `riser_room` | Riser Room | Pink |

## PathwayTypeChoices

| Value | Label | Color |
|-------|-------|-------|
| `conduit` | Conduit | Brown |
| `aerial` | Aerial | Blue |
| `direct_buried` | Direct Buried | Gray |
| `innerduct` | Innerduct | Orange |
| `microduct` | Microduct | Purple |
| `tray` | Cable Tray | Green |
| `raceway` | Raceway | Cyan |
| `submarine` | Submarine | Navy |

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
