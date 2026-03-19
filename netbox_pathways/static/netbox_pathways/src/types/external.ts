export interface ExternalLayerStyle {
  color: string;
  colorField: string | null;
  colorMap: Record<string, string> | null;
  defaultColor: string;
  icon: string | null;
  dash: string | null;
  weight: number;
  opacity: number;
}

export interface ExternalLayerDetail {
  urlTemplate: string;
  fields: string[];
  labelField: string;
}

export interface ExternalLayerConfig {
  name: string;
  label: string;
  geometryType: 'Point' | 'LineString' | 'Polygon';
  url: string;
  style: ExternalLayerStyle;
  detail?: ExternalLayerDetail;
  popoverFields: string[];
  defaultVisible: boolean;
  group: string;
  minZoom: number;
  maxZoom: number | null;
  sortOrder: number;
}
