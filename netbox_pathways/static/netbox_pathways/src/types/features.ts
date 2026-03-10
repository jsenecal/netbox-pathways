/** Shared types for map features and sidebar entries. */

export interface GeoJSONProperties {
  id: number;
  name: string;
  url: string;
  structure_type?: string;
  pathway_type?: string;
  site_name?: string;
  cluster?: boolean;
  point_count?: number;
  [key: string]: unknown;
}

export type FeatureType = 'structure' | 'conduit' | 'aerial' | 'direct_buried';

export interface FeatureEntry {
  props: GeoJSONProperties;
  featureType: FeatureType;
  layer: L.Layer;
  latlng: L.LatLng;
}

export type DetailFieldDef = [string, string] | [string, string, string];

export interface ResolvedValue {
  text: string;
  url?: string | null;
}

export interface PathwayStyle {
  color: string;
  weight: number;
  opacity: number;
  dashArray: string;
}

export interface PathwayLayerConfig {
  endpoint: string;
  layer: L.LayerGroup;
  featureType: FeatureType;
  style: PathwayStyle;
}
