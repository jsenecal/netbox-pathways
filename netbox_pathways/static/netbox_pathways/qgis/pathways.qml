<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology|Labeling">
  <!--
    QGIS style for the Pathways GeoJSON layer.
    Categorized symbology by pathway_type with utilization-based line width.
    Load via: Layer Properties > Style > Load Style
  -->
  <renderer-v2 type="categorizedSymbol" attr="pathway_type" symbollevels="0">
    <categories>
      <category symbol="0" value="conduit" label="Conduit" render="true"/>
      <category symbol="1" value="aerial" label="Aerial" render="true"/>
      <category symbol="2" value="direct_buried" label="Direct Buried" render="true"/>
      <category symbol="3" value="innerduct" label="Innerduct" render="true"/>
      <category symbol="4" value="tray" label="Cable Tray" render="true"/>
      <category symbol="5" value="raceway" label="Raceway" render="true"/>
      <category symbol="6" value="" label="Unknown" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="line"><layer class="SimpleLine"><prop k="line_color" v="139,69,19,255"/><prop k="line_width" v="0.8"/><prop k="line_style" v="solid"/></layer></symbol>
      <symbol name="1" type="line"><layer class="SimpleLine"><prop k="line_color" v="0,0,255,255"/><prop k="line_width" v="0.6"/><prop k="line_style" v="dash"/></layer></symbol>
      <symbol name="2" type="line"><layer class="SimpleLine"><prop k="line_color" v="128,128,128,255"/><prop k="line_width" v="0.8"/><prop k="line_style" v="dot"/></layer></symbol>
      <symbol name="3" type="line"><layer class="SimpleLine"><prop k="line_color" v="255,165,0,255"/><prop k="line_width" v="0.5"/><prop k="line_style" v="solid"/></layer></symbol>
      <symbol name="4" type="line"><layer class="SimpleLine"><prop k="line_color" v="0,128,0,255"/><prop k="line_width" v="0.8"/><prop k="line_style" v="solid"/></layer></symbol>
      <symbol name="5" type="line"><layer class="SimpleLine"><prop k="line_color" v="75,0,130,255"/><prop k="line_width" v="0.6"/><prop k="line_style" v="solid"/></layer></symbol>
      <symbol name="6" type="line"><layer class="SimpleLine"><prop k="line_color" v="128,128,128,200"/><prop k="line_width" v="0.4"/><prop k="line_style" v="dash"/></layer></symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings>
      <text-style fieldName="name" fontSize="7" fontFamily="Sans Serif" textColor="0,0,0,255"/>
      <placement placement="3" dist="0.5"/>
    </settings>
  </labeling>
</qgis>
