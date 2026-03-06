"""
SVG generation utilities for fiber splice diagrams
"""
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from dcim.models import Device, FrontPort, Cable
from .models import SpliceConnection, FiberCable


class SpliceDiagramSVG:
    """Generate SVG diagrams for splice closures and fiber connections"""
    
    def __init__(self, device: Device, width: int = 1200, height: int = 800):
        self.device = device
        self.width = width
        self.height = height
        self.svg = None
        self.fiber_height = 20  # Height per fiber
        self.port_width = 120   # Width of port column
        self.splice_area_width = 200  # Width of splice area in middle
        
    def generate(self) -> str:
        """Generate complete SVG diagram for device splices"""
        # Create SVG root element
        self.svg = ET.Element('svg', {
            'width': str(self.width),
            'height': str(self.height),
            'viewBox': f'0 0 {self.width} {self.height}',
            'xmlns': 'http://www.w3.org/2000/svg'
        })
        
        # Add title
        self._add_title()
        
        # Get all ports and splices
        front_ports = FrontPort.objects.filter(device=self.device).order_by('name')
        splice_connections = SpliceConnection.objects.filter(device=self.device)
        
        # Group ports by cable (incoming vs outgoing)
        incoming_ports = []
        outgoing_ports = []
        
        for port in front_ports:
            if port.cable:
                # Check if this is incoming or outgoing based on termination side
                if hasattr(port.cable, 'termination_a') and port == port.cable.termination_a:
                    incoming_ports.append(port)
                else:
                    outgoing_ports.append(port)
        
        # Draw port groups
        self._draw_port_group(incoming_ports, 50, 100, "Incoming Fibers")
        self._draw_port_group(outgoing_ports, self.width - self.port_width - 50, 100, "Outgoing Fibers")
        
        # Draw splice connections
        self._draw_splices(splice_connections)
        
        # Draw legend
        self._add_legend()
        
        return ET.tostring(self.svg, encoding='unicode')
    
    def _add_title(self):
        """Add title to the SVG"""
        title = ET.SubElement(self.svg, 'text', {
            'x': str(self.width // 2),
            'y': '30',
            'text-anchor': 'middle',
            'font-size': '24',
            'font-weight': 'bold',
            'fill': '#333'
        })
        title.text = f"Splice Diagram: {self.device.name}"
        
        subtitle = ET.SubElement(self.svg, 'text', {
            'x': str(self.width // 2),
            'y': '55',
            'text-anchor': 'middle',
            'font-size': '14',
            'fill': '#666'
        })
        subtitle.text = f"Site: {self.device.site.name} | Type: {self.device.device_type.model}"
    
    def _draw_port_group(self, ports: List[FrontPort], x: int, y: int, label: str):
        """Draw a group of ports"""
        # Group label
        group_label = ET.SubElement(self.svg, 'text', {
            'x': str(x + self.port_width // 2),
            'y': str(y - 10),
            'text-anchor': 'middle',
            'font-size': '16',
            'font-weight': 'bold',
            'fill': '#333'
        })
        group_label.text = label
        
        # Draw each port
        for i, port in enumerate(ports):
            port_y = y + (i * self.fiber_height)
            
            # Port rectangle
            rect = ET.SubElement(self.svg, 'rect', {
                'x': str(x),
                'y': str(port_y),
                'width': str(self.port_width),
                'height': str(self.fiber_height - 2),
                'fill': self._get_port_color(port),
                'stroke': '#333',
                'stroke-width': '1',
                'data-port-id': str(port.id)
            })
            
            # Port label
            text = ET.SubElement(self.svg, 'text', {
                'x': str(x + 5),
                'y': str(port_y + 14),
                'font-size': '12',
                'fill': '#000'
            })
            text.text = port.name
            
            # Cable info if available
            if port.cable:
                cable_text = ET.SubElement(self.svg, 'text', {
                    'x': str(x + self.port_width - 5),
                    'y': str(port_y + 14),
                    'font-size': '10',
                    'text-anchor': 'end',
                    'fill': '#666'
                })
                cable_text.text = port.cable.label[:10]
    
    def _draw_splices(self, splices: List[SpliceConnection]):
        """Draw splice connections between ports"""
        for splice in splices:
            # Find positions of connected ports
            a_pos = self._get_port_position(splice.a_port)
            b_pos = self._get_port_position(splice.b_port)
            
            if a_pos and b_pos:
                # Draw splice path
                path_data = self._create_splice_path(a_pos, b_pos)
                path = ET.SubElement(self.svg, 'path', {
                    'd': path_data,
                    'fill': 'none',
                    'stroke': self._get_splice_color(splice),
                    'stroke-width': '2',
                    'opacity': '0.8'
                })
                
                # Add splice point marker
                mid_x = (a_pos[0] + b_pos[0]) // 2
                mid_y = (a_pos[1] + b_pos[1]) // 2
                
                if splice.splice_type == 'fusion':
                    # Fusion splice - small circle
                    ET.SubElement(self.svg, 'circle', {
                        'cx': str(mid_x),
                        'cy': str(mid_y),
                        'r': '3',
                        'fill': '#ff6600',
                        'stroke': '#333',
                        'stroke-width': '1'
                    })
                elif splice.splice_type == 'mechanical':
                    # Mechanical splice - small square
                    ET.SubElement(self.svg, 'rect', {
                        'x': str(mid_x - 3),
                        'y': str(mid_y - 3),
                        'width': '6',
                        'height': '6',
                        'fill': '#0099ff',
                        'stroke': '#333',
                        'stroke-width': '1'
                    })
    
    def _create_splice_path(self, start: Tuple[int, int], end: Tuple[int, int]) -> str:
        """Create curved path for splice connection"""
        # Create a smooth bezier curve
        mid_x = (start[0] + end[0]) // 2
        
        path = f"M {start[0]} {start[1]} "
        path += f"C {mid_x} {start[1]}, {mid_x} {end[1]}, {end[0]} {end[1]}"
        
        return path
    
    def _get_port_position(self, port: FrontPort) -> Tuple[int, int]:
        """Get x,y position of a port in the diagram"""
        # This is simplified - in real implementation would track actual positions
        # For now, return estimated position based on port index
        ports = list(FrontPort.objects.filter(device=self.device).order_by('name'))
        
        try:
            index = ports.index(port)
            # Determine if incoming or outgoing
            if hasattr(port.cable, 'termination_a') and port == port.cable.termination_a:
                # Incoming - left side
                x = 50 + self.port_width
                y = 100 + (index * self.fiber_height) + (self.fiber_height // 2)
            else:
                # Outgoing - right side
                x = self.width - self.port_width - 50
                y = 100 + (index * self.fiber_height) + (self.fiber_height // 2)
            return (x, y)
        except (ValueError, AttributeError):
            return None
    
    def _get_port_color(self, port: FrontPort) -> str:
        """Get color for port based on fiber type"""
        if port.cable and hasattr(port.cable, 'fiber_cable'):
            fiber_cable = port.cable.fiber_cable
            if fiber_cable.fiber_type == 'sm':
                return '#ffff99'  # Yellow for single mode
            elif 'om3' in fiber_cable.fiber_type or 'om4' in fiber_cable.fiber_type:
                return '#99ffff'  # Aqua for OM3/OM4
            else:
                return '#ffcc99'  # Orange for other multimode
        return '#f0f0f0'  # Gray for unknown
    
    def _get_splice_color(self, splice: SpliceConnection) -> str:
        """Get color for splice based on type"""
        colors = {
            'fusion': '#ff6600',
            'mechanical': '#0099ff',
            'pigtail': '#00cc00',
            'patch': '#cc00cc'
        }
        return colors.get(splice.splice_type, '#666666')
    
    def _add_legend(self):
        """Add legend to the diagram"""
        legend_x = self.width - 200
        legend_y = self.height - 150
        
        # Legend box
        ET.SubElement(self.svg, 'rect', {
            'x': str(legend_x),
            'y': str(legend_y),
            'width': '180',
            'height': '130',
            'fill': 'white',
            'stroke': '#333',
            'stroke-width': '1'
        })
        
        # Legend title
        title = ET.SubElement(self.svg, 'text', {
            'x': str(legend_x + 90),
            'y': str(legend_y + 20),
            'text-anchor': 'middle',
            'font-size': '14',
            'font-weight': 'bold',
            'fill': '#333'
        })
        title.text = "Legend"
        
        # Fiber types
        legend_items = [
            ('Single Mode', '#ffff99'),
            ('Multimode OM3/4', '#99ffff'),
            ('Multimode OM1/2', '#ffcc99'),
        ]
        
        for i, (label, color) in enumerate(legend_items):
            y_pos = legend_y + 40 + (i * 20)
            
            # Color box
            ET.SubElement(self.svg, 'rect', {
                'x': str(legend_x + 10),
                'y': str(y_pos - 10),
                'width': '15',
                'height': '15',
                'fill': color,
                'stroke': '#333',
                'stroke-width': '1'
            })
            
            # Label
            text = ET.SubElement(self.svg, 'text', {
                'x': str(legend_x + 30),
                'y': str(y_pos),
                'font-size': '12',
                'fill': '#333'
            })
            text.text = label
        
        # Splice types
        splice_items = [
            ('Fusion', 'circle', '#ff6600'),
            ('Mechanical', 'rect', '#0099ff'),
        ]
        
        for i, (label, shape, color) in enumerate(splice_items):
            y_pos = legend_y + 100 + (i * 20)
            
            if shape == 'circle':
                ET.SubElement(self.svg, 'circle', {
                    'cx': str(legend_x + 17),
                    'cy': str(y_pos - 3),
                    'r': '5',
                    'fill': color,
                    'stroke': '#333',
                    'stroke-width': '1'
                })
            else:
                ET.SubElement(self.svg, 'rect', {
                    'x': str(legend_x + 12),
                    'y': str(y_pos - 8),
                    'width': '10',
                    'height': '10',
                    'fill': color,
                    'stroke': '#333',
                    'stroke-width': '1'
                })
            
            # Label
            text = ET.SubElement(self.svg, 'text', {
                'x': str(legend_x + 30),
                'y': str(y_pos),
                'font-size': '12',
                'fill': '#333'
            })
            text.text = label


def generate_splice_diagram(device_id: int) -> str:
    """Generate SVG splice diagram for a device"""
    try:
        device = Device.objects.get(pk=device_id)
        generator = SpliceDiagramSVG(device)
        return generator.generate()
    except Device.DoesNotExist:
        return None