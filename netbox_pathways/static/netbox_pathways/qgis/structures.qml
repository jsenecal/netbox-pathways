<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology|Labeling">
  <!--
    QGIS style for the Structures GeoJSON layer.
    Categorized symbology by structure_type with labeling on name.
    Load via: Layer Properties > Style > Load Style
  -->
  <renderer-v2 type="categorizedSymbol" attr="structure_type" symbollevels="0">
    <categories>
      <category symbol="0" value="pole" label="Pole" render="true"/>
      <category symbol="1" value="manhole" label="Manhole" render="true"/>
      <category symbol="2" value="handhole" label="Handhole" render="true"/>
      <category symbol="3" value="cabinet" label="Cabinet" render="true"/>
      <category symbol="4" value="building_entrance" label="Building Entrance" render="true"/>
      <category symbol="5" value="equipment_room" label="Equipment Room" render="true"/>
      <category symbol="6" value="telecom_closet" label="Telecom Closet" render="true"/>
      <category symbol="7" value="riser_room" label="Riser Room" render="true"/>
      <category symbol="8" value="" label="Unknown" render="true"/>
    </categories>
    <symbols>
      <symbol name="0" type="marker"><layer class="SimpleMarker"><prop k="color" v="34,139,34,255"/><prop k="size" v="3"/><prop k="name" v="circle"/></layer></symbol>
      <symbol name="1" type="marker"><layer class="SimpleMarker"><prop k="color" v="0,0,255,255"/><prop k="size" v="4"/><prop k="name" v="square"/></layer></symbol>
      <symbol name="2" type="marker"><layer class="SimpleMarker"><prop k="color" v="0,191,255,255"/><prop k="size" v="3"/><prop k="name" v="diamond"/></layer></symbol>
      <symbol name="3" type="marker"><layer class="SimpleMarker"><prop k="color" v="255,165,0,255"/><prop k="size" v="3.5"/><prop k="name" v="square"/></layer></symbol>
      <symbol name="4" type="marker"><layer class="SimpleMarker"><prop k="color" v="220,20,60,255"/><prop k="size" v="3.5"/><prop k="name" v="triangle"/></layer></symbol>
      <symbol name="5" type="marker"><layer class="SimpleMarker"><prop k="color" v="128,0,128,255"/><prop k="size" v="4"/><prop k="name" v="square"/></layer></symbol>
      <symbol name="6" type="marker"><layer class="SimpleMarker"><prop k="color" v="70,130,180,255"/><prop k="size" v="3"/><prop k="name" v="diamond"/></layer></symbol>
      <symbol name="7" type="marker"><layer class="SimpleMarker"><prop k="color" v="139,69,19,255"/><prop k="size" v="3"/><prop k="name" v="triangle"/></layer></symbol>
      <symbol name="8" type="marker"><layer class="SimpleMarker"><prop k="color" v="128,128,128,255"/><prop k="size" v="2.5"/><prop k="name" v="circle"/></layer></symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings>
      <text-style fieldName="name" fontSize="8" fontFamily="Sans Serif" textColor="0,0,0,255"/>
      <placement placement="2" dist="1.5"/>
    </settings>
  </labeling>
</qgis>
