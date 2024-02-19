"""
    Generate JST SH wire-to-board female connectors

    see 
        https://en.wikipedia.org/wiki/JST_connector, https://jst.de/product-family/show/65/sh
    
"""
from os import path
from uuid import uuid4
import math

from typing import Iterable, List, Optional

from common import init_cache, now, save_cache
from entities.common import (
    Align, Angle, Author, Category, Created, Deprecated, Description, Fill, GrabArea, Height, Keywords, Layer,
    Name, Polygon, Position, Rotation, Value, Version, Vertex, Width, GeneratedBy, Circle, Diameter
)
from entities.component import (SignalUUID)
from entities.package import (
    AutoRotate, FootprintPad, LetterSpacing, LineSpacing, Mirror, Package, PackagePad, Footprint, Shape, ShapeRadius, ComponentSide, Size, StrokeText, StrokeWidth, AssemblyType, Position3D, Rotation3D, StopMaskConfig, SolderPasteConfig, CopperClearance, PadFunction, PackagePadUuid
)
from entities.device import (
    ComponentPad,
    ComponentUUID,
    Device,
    PackageUUID
)


generator = 'librepcb-parts-generator (generate_jst_sh_connectors.py)'

# configurable params
text_height = 1.0
text_stroke_width = 0.2
text_header_spacing = 1
courtyard_excess = 0.2
header_line_width = 0.25
legend_header_spacing = 0.1
legend_line_width = 0.2
legend_pin_one_dot_diameter = 0.35

uuid_cache_file = 'uuid_cache_jst_sh_connectors.csv'
uuid_cache = init_cache(uuid_cache_file)


class Connector:
    def __init__(self, type: str, subtype: str, circuits: int) -> None:
        self.type = type
        self.subtype = subtype
        self.circuits = circuits


class FootprintSpecification:
    def __init__(self,
                 pad_width: float,
                 pad_height: float,
                 lead_width: float,
                 lead_height: float,
                 support_pad_width: float,
                 support_pad_height: float,
                 smallest_header_width: float,
                 header_width_increase_per_pin: float,
                 header_height: float,
                 pad_distance_mid_to_mid_x: float,
                 pad_first_x_center: float,
                 pad_first_y_center: float,
                 header_y: float
                 ):
        self.pad_width = pad_width
        self.pad_height = pad_height
        self.lead_width = lead_width
        self.lead_height = lead_height
        self.support_pad_width = support_pad_width
        self.support_pad_height = support_pad_height
        self.smallest_header_width = smallest_header_width
        self.header_width_increase_per_pin = header_width_increase_per_pin
        self.header_height = header_height
        self.pad_distance_mid_to_mid_x = pad_distance_mid_to_mid_x
        self.pad_first_x_center = pad_first_x_center
        self.pad_first_y_center = pad_first_y_center
        self.header_y = header_y
        self.header_y_center = self.header_y + (self.header_height / 2)

        self.support_pad_edge_to_pad_edge = self.pad_first_x_center - self.support_pad_width

        self.support_pad_first_x_center = self.support_pad_width / 2  # account for center origin
        self.support_pad_first_y_center = self.support_pad_height / 2  # account for center origin

    # we define the following attributes as functions since they depend on the pin count

    def header_width(self, circuits: int) -> float:
        return self.smallest_header_width + (circuits - 2) * self.header_width_increase_per_pin

    def support_pad_distance_x(self, circuits: int) -> float:
        return self.pad_first_x_center + (circuits - 1) * self.pad_distance_mid_to_mid_x + self.support_pad_edge_to_pad_edge

    def header_x(self, circuits: int) -> float:
        return (self.support_pad_width + self.support_pad_distance_x(circuits) - self.header_width(circuits)) / 2

    def header_x_center(self, circuits: int) -> float:
        return self.header_x(circuits) + (self.header_width(circuits) / 2)


# we need some way of looking up the Connectors from LibrePCB Connectors library.
def lookup_connector_component(rows: int, circuits: int) -> str:
    with open(path.join('uuid_cache_connectors.csv'), 'r') as f:
        lines = f.readlines()
        for l in lines:
            if l.startswith(f'cmp-pinheader-{rows}x{circuits}-cmp,'):
                return l.split(',')[1][:-1]

        print(f'error! could not find connector symbol for {rows}x{circuits}')
        exit(1)


def lookup_connector_component_signal(rows: int, circuits: int) -> List[str]:
    found = [''] * circuits
    with open(path.join('uuid_cache_connectors.csv'), 'r') as f:
        lines = f.readlines()
        for l in lines:
            for i in range(circuits):
                if l.startswith(f'cmp-pinheader-{rows}x{circuits}-signal-{i},'):
                    found[i] = l.split(',')[1][:-1]

        for i in range(circuits):
            if found[i] == '':
                print(f'error! could not find pin connector symbol for {rows}x{circuits} signal {i}')
                exit(1)

        return found


def variant(mounting_variant: str, circuits: int) -> str:
    return f"{mounting_variant}{circuits}"


def uuid(category: str, kind: str, variant: str, identifier: str) -> str:
    key = '{}-{}-{}-{}'.format(category, kind, variant, identifier).lower().replace(' ', '~')
    if key not in uuid_cache:
        uuid_cache[key] = str(uuid4())
    return uuid_cache[key]


def connector_uuid(category: str, connector: Connector, identifier: str) -> str:
    return uuid(category, connector.type, variant(connector.subtype, connector.circuits), identifier)


def pkg_uuid(connector: Connector, identifier: str) -> str:
    return connector_uuid("pkg", connector, identifier)


def footprint_uuid(connector: Connector, identifier: str) -> str:
    return connector_uuid("footprint", connector, identifier)


def dev_uuid(connector: Connector, identifier: str) -> str:
    return connector_uuid("dev", connector, identifier)


def write_pkg(library: str, pkg: Package) -> None:
    pkg.serialize(path.join('out', library, 'pkg'))
    print(f'wrote package {pkg.name.value}: {pkg.uuid}')


def write_dev(library: str, dev: Device) -> None:
    dev.serialize(path.join('out', library, 'dev'))
    print(f'wrote device {dev.name.value}: {dev.uuid}')


def vertex(x: float, y: float) -> Vertex:
    return Vertex(Position(x, y), Angle(0))


def polygon_rect(polygon: Polygon, x: float, y: float, w: float, h: float) -> None:
    polygon.add_vertex(Vertex(Position(x, y), Angle(0)))
    polygon.add_vertex(Vertex(Position(x + w, y), Angle(0)))
    polygon.add_vertex(Vertex(Position(x + w, y + h), Angle(0)))
    polygon.add_vertex(Vertex(Position(x, y + h), Angle(0)))
    polygon.add_vertex(Vertex(Position(x, y), Angle(0)))


def footprint_add_support_pads(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:
    for i in range(2):
        footprint.add_pad(
            FootprintPad(
                uuid=footprint_uuid(connector, f'supportpad{i}'),
                side=ComponentSide.TOP,
                shape=Shape.ROUNDED_RECT,
                position=Position(spec.support_pad_first_x_center + i * spec.support_pad_distance_x(connector.circuits), spec.support_pad_first_y_center),
                rotation=Rotation(0),
                size=Size(spec.support_pad_width, spec.support_pad_height),
                radius=ShapeRadius(0.5),  # 0.5 is default
                stop_mask=StopMaskConfig.AUTO,
                solder_paste=SolderPasteConfig.AUTO,
                copper_clearance=CopperClearance(0),
                function=PadFunction.STANDARD_PAD,
                package_pad=PackagePadUuid("none"),  # not connected, mechanical pad
                holes=[]
            )
        )


def footprint_add_pads(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification,
    reverse_pad_order: bool
) -> None:
    for i in range(connector.circuits):
        pad_number = i if not reverse_pad_order else (connector.circuits - 1) - i
        footprint.add_pad(
            FootprintPad(
                uuid=footprint_uuid(connector, f'pad{pad_number}'),
                side=ComponentSide.TOP,
                shape=Shape.ROUNDED_RECT,
                position=Position(spec.pad_first_x_center + i * spec.pad_distance_mid_to_mid_x, spec.pad_first_y_center),
                rotation=Rotation(0),
                size=Size(spec.pad_width, spec.pad_height),
                radius=ShapeRadius(0.5),  # 0.5 is default
                stop_mask=StopMaskConfig.AUTO,
                solder_paste=SolderPasteConfig.AUTO,
                copper_clearance=CopperClearance(0),
                function=PadFunction.STANDARD_PAD,
                package_pad=PackagePadUuid(pkg_uuid(connector, f'pad{pad_number}')),
                holes=[]
            )
        )


def footprint_add_header(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:
    header_half_line_width = header_line_width / 2

    header_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygonheader'),
        layer=Layer("top_documentation"),
        width=Width(header_line_width),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    # NOTE: lines in librePCB expand equally on each
    # side if drawn with a width of > 0
    polygon_rect(header_polygon,
                 spec.header_x(connector.circuits) + header_half_line_width,
                 spec.header_y + header_half_line_width,
                 spec.header_width(connector.circuits) - header_half_line_width * 2,
                 spec.header_height - header_half_line_width * 2)

    footprint.add_polygon(header_polygon)


def footprint_add_text(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:

    # NOTE: Alignment and Position was chosen based on how the whole package looks when shifted to center + rotated 90 degrees

    name_text = StrokeText(
        uuid=footprint_uuid(connector, 'textname'),
        layer=Layer('top_names'),
        height=Height(text_height),
        stroke_width=StrokeWidth(text_stroke_width),
        letter_spacing=LetterSpacing.AUTO,
        line_spacing=LineSpacing.AUTO,
        align=Align('center bottom'),
        position=Position(spec.header_x_center(connector.circuits) - (spec.header_width(connector.circuits) / 2) - text_header_spacing, spec.header_y_center),
        rotation=Rotation(0),
        auto_rotate=AutoRotate(True),
        mirror=Mirror(False),
        value=Value('{{NAME}}')
    )

    value_text = StrokeText(
        uuid=footprint_uuid(connector, 'textvalue'),
        layer=Layer('top_values'),
        height=Height(text_height),
        stroke_width=StrokeWidth(text_stroke_width),
        letter_spacing=LetterSpacing.AUTO,
        line_spacing=LineSpacing.AUTO,
        align=Align('center top'),
        position=Position(spec.header_x_center(connector.circuits) + (spec.header_width(connector.circuits) / 2) + text_header_spacing, spec.header_y_center),
        rotation=Rotation(0),
        auto_rotate=AutoRotate(True),
        mirror=Mirror(False),
        value=Value('{{VALUE}}')
    )

    footprint.add_text(name_text)
    footprint.add_text(value_text)


def footprint_add_leads(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:

    for i in range(connector.circuits):

        lead_polygon = Polygon(
            uuid=footprint_uuid(connector, f"lead{i}"),
            layer=Layer('top_documentation'),
            width=Width(0),
            fill=Fill(True),
            grab_area=GrabArea(False)
        )

        polygon_rect(lead_polygon,
                     spec.pad_first_x_center - (spec.lead_width / 2) + i * spec.pad_distance_mid_to_mid_x,
                     spec.header_y + spec.header_height,
                     spec.lead_width,
                     spec.lead_height
                     )

        footprint.add_polygon(lead_polygon)


def footprint_add_outline(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:

    outline_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygonoutline'),
        layer=Layer('top_package_outlines'),
        width=Width(0),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    # left bottom
    outline_polygon.add_vertex(vertex(spec.header_x(connector.circuits), spec.header_y))
    # right bottom
    outline_polygon.add_vertex(vertex(spec.header_x(connector.circuits) + spec.header_width(connector.circuits), spec.header_y))
    # right top
    outline_polygon.add_vertex(vertex(spec.header_x(connector.circuits) + spec.header_width(connector.circuits), spec.header_y + spec.header_height))
    # leads
    outline_polygon.add_vertex(vertex(spec.pad_first_x_center + (spec.pad_distance_mid_to_mid_x * (connector.circuits - 1)) + (spec.pad_width / 2), spec.header_y + spec.header_height))
    outline_polygon.add_vertex(vertex(spec.pad_first_x_center + (spec.pad_distance_mid_to_mid_x * (connector.circuits - 1)) + (spec.pad_width / 2), spec.header_y + spec.header_height + spec.lead_height))
    outline_polygon.add_vertex(vertex(spec.pad_first_x_center - (spec.pad_width / 2), spec.header_y + spec.lead_height + spec.header_height))
    outline_polygon.add_vertex(vertex(spec.pad_first_x_center - (spec.pad_width / 2), spec.header_y + spec.header_height))
    # left top
    outline_polygon.add_vertex(vertex(spec.header_x(connector.circuits), spec.header_y + spec.header_height))
    # left bottom
    outline_polygon.add_vertex(vertex(spec.header_x(connector.circuits), spec.header_y))

    footprint.add_polygon(outline_polygon)


def footprint_add_courtyard(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification
) -> None:
    courtyard_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygoncourtyard'),
        layer=Layer('top_courtyard'),
        width=Width(0),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    # left bottom
    courtyard_polygon.add_vertex(vertex(0 - courtyard_excess, 0 - courtyard_excess))
    # right bottom
    courtyard_polygon.add_vertex(vertex(spec.support_pad_distance_x(connector.circuits) + spec.support_pad_width + courtyard_excess, 0 - courtyard_excess))
    # right top
    courtyard_polygon.add_vertex(vertex(spec.support_pad_distance_x(connector.circuits) + spec.support_pad_width + courtyard_excess, spec.header_y + spec.header_height + courtyard_excess))
    # leads
    courtyard_polygon.add_vertex(vertex(spec.pad_first_x_center + (spec.pad_distance_mid_to_mid_x * (connector.circuits - 1)) + (spec.pad_width / 2) + courtyard_excess, spec.header_y + spec.header_height + courtyard_excess))
    courtyard_polygon.add_vertex(vertex(spec.pad_first_x_center + (spec.pad_distance_mid_to_mid_x * (connector.circuits - 1)) + (spec.pad_width / 2) + courtyard_excess, spec.pad_first_y_center + (spec.pad_height / 2) + courtyard_excess))
    courtyard_polygon.add_vertex(vertex(spec.pad_first_x_center - (spec.pad_width / 2) - courtyard_excess, spec.pad_first_y_center + (spec.pad_height / 2) + courtyard_excess))
    courtyard_polygon.add_vertex(vertex(spec.pad_first_x_center - (spec.pad_width / 2) - courtyard_excess, spec.header_y + spec.header_height + courtyard_excess))
    # left top
    courtyard_polygon.add_vertex(vertex(0 - courtyard_excess, spec.header_y + spec.header_height + courtyard_excess))
    # left bottom
    courtyard_polygon.add_vertex(vertex(0 - courtyard_excess, 0 - courtyard_excess))

    footprint.add_polygon(courtyard_polygon)


def footprint_add_legend(
    footprint: Footprint,
    connector: Connector,
    spec: FootprintSpecification,
    reverse_pad_order: bool
) -> None:

    half_line_width = legend_line_width / 2
    min_copper_clearance = 0.15

    top_left_legend_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygonlegendtopleft'),
        layer=Layer('top_legend'),
        width=Width(legend_line_width),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    top_left_legend_polygon.add_vertex(vertex(
        spec.header_x(connector.circuits) - legend_header_spacing - half_line_width,
        spec.support_pad_first_y_center + (spec.support_pad_height / 2) + half_line_width + max(min_copper_clearance, legend_line_width)
    ))

    top_left_legend_polygon.add_vertex(vertex(
        spec.header_x(connector.circuits) - legend_header_spacing - half_line_width,
        spec.header_y + spec.header_height + legend_header_spacing + half_line_width
    ))

    top_left_legend_polygon.add_vertex(vertex(
        spec.pad_first_x_center - (spec.pad_width / 2) - half_line_width - max(min_copper_clearance, legend_line_width),
        spec.header_y + spec.header_height + legend_header_spacing + half_line_width
    ))

    footprint.add_polygon(top_left_legend_polygon)

    top_right_legend_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygonlegendtopright'),
        layer=Layer('top_legend'),
        width=Width(legend_line_width),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    top_right_legend_polygon.add_vertex(vertex(
        spec.header_x(connector.circuits) + spec.header_width(connector.circuits) + legend_header_spacing + half_line_width,
        spec.support_pad_first_y_center + (spec.support_pad_height / 2) + half_line_width + max(min_copper_clearance, legend_line_width)
    ))

    top_right_legend_polygon.add_vertex(vertex(
        spec.header_x(connector.circuits) + spec.header_width(connector.circuits) + legend_header_spacing + half_line_width,
        spec.header_y + spec.header_height + legend_header_spacing + half_line_width
    ))

    top_right_legend_polygon.add_vertex(vertex(
        spec.pad_first_x_center + spec.pad_distance_mid_to_mid_x * (connector.circuits - 1) + (spec.pad_width / 2) + half_line_width + max(min_copper_clearance, legend_line_width),
        spec.header_y + spec.header_height + legend_header_spacing + half_line_width
    ))

    footprint.add_polygon(top_right_legend_polygon)

    bottom_center_legend_polygon = Polygon(
        uuid=footprint_uuid(connector, 'polygonlegendbottomcenter'),
        layer=Layer('top_legend'),
        width=Width(legend_line_width),
        fill=Fill(False),
        grab_area=GrabArea(False)
    )

    bottom_center_legend_polygon.add_vertex(vertex(
        spec.support_pad_first_x_center + (spec.support_pad_width / 2) + half_line_width + max(min_copper_clearance, legend_line_width),
        spec.header_y - half_line_width - legend_header_spacing
    ))

    bottom_center_legend_polygon.add_vertex(vertex(
        spec.support_pad_distance_x(connector.circuits) - half_line_width - max(min_copper_clearance, legend_line_width),
        spec.header_y - half_line_width - legend_header_spacing
    ))

    footprint.add_polygon(bottom_center_legend_polygon)

    pin_one_dot_half_diameter = legend_pin_one_dot_diameter / 2
    pin_one_dot_x: float = 0

    if reverse_pad_order:
        # draw dot top right
        pin_one_dot_x = (spec.pad_first_x_center +
                         spec.pad_distance_mid_to_mid_x * (connector.circuits - 1) +
                         (spec.pad_width / 2) +
                         min_copper_clearance +
                         pin_one_dot_half_diameter)
    else:
        # draw dot top left
        pin_one_dot_x = (spec.pad_first_x_center -
                         (spec.pad_width / 2) -
                         min_copper_clearance -
                         pin_one_dot_half_diameter)

    pin_one_dot = Circle(
        uuid=footprint_uuid(connector, 'circlepinone'),
        layer=Layer('top_legend'),
        width=Width(0),
        fill=Fill(True),
        grab_area=GrabArea(False),
        diameter=Diameter(legend_pin_one_dot_diameter),
        position=Position(pin_one_dot_x, spec.pad_first_y_center + (spec.pad_height / 4))
    )

    footprint.add_circle(pin_one_dot)


def generate_footprint(
    connector: Connector,
    spec: FootprintSpecification,
    description: str,
    reverse_pad_order: bool
) -> Footprint:

    footprint = Footprint(
        uuid=footprint_uuid(connector, 'footprint'),
        name=Name("default"),
        description=Description(description),
        position_3d=Position3D.zero(),
        rotation_3d=Rotation3D.zero()
    )

    footprint_add_support_pads(footprint, connector, spec)
    footprint_add_pads(footprint, connector, spec, reverse_pad_order)
    footprint_add_header(footprint, connector, spec)
    footprint_add_text(footprint, connector, spec)
    footprint_add_leads(footprint, connector, spec)
    footprint_add_outline(footprint, connector, spec)
    footprint_add_courtyard(footprint, connector, spec)
    footprint_add_legend(footprint, connector, spec, reverse_pad_order)

    # shift to center since we drew the package in the first quadrant
    footprint_shift_to_center(footprint, connector, spec)
    # rotate around center to have the pads on the left side (as per library conventions)
    footprint_rotate_around_center(footprint, 90)

    return footprint


# shift all members inside a Footprint with a position to the center
# ASSUMES that the current origin/center is in the first quadrant
def footprint_shift_to_center(footprint: Footprint, connector: Connector, spec: FootprintSpecification) -> None:

    def _center(p: Position) -> None:
        p.x -= spec.header_x_center(connector.circuits)
        p.y -= spec.header_y_center

    for pad in footprint.pads:
        _center(pad.position)

    for text in footprint.texts:
        _center(text.position)

    for polygon in footprint.polygons:
        for vertex in polygon.vertices:
            _center(vertex.position)

    for circle in footprint.circles:
        _center(circle.position)


def footprint_rotate_around_center(footprint: Footprint, angle_deg: int) -> None:

    angle_rad = math.radians(angle_deg)

    def _rotate(p: Position) -> None:
        x, y = p.x, p.y
        p.x = x * math.cos(angle_rad) - y * math.sin(angle_rad)
        p.y = y * math.cos(angle_rad) - x * math.sin(angle_rad)

    for pad in footprint.pads:
        _rotate(pad.position)
        pad.rotation.value = angle_deg

    for text in footprint.texts:
        _rotate(text.position)

    for polygon in footprint.polygons:
        for vertex in polygon.vertices:
            _rotate(vertex.position)

    for circle in footprint.circles:
        _rotate(circle.position)


def generate_pkg(
    connector: Connector,
    description: str,
    keywords: str,
    author: str,
    pkgcat: str,
    version: str,
    create_date: Optional[str],
    generated_by: str,
    footprint_spec: FootprintSpecification,
    reverse_pad_order: bool
) -> Package:

    package = Package(
        uuid=pkg_uuid(connector, 'pkg'),
        name=Name(f"JST {connector.type}-{connector.subtype}-{connector.circuits:02d}"),
        description=Description(description),
        keywords=Keywords(keywords),
        author=Author(author),
        version=Version(version),
        created=Created(create_date or now()),
        deprecated=Deprecated(False),
        generated_by=GeneratedBy(generated_by),
        categories=[Category(pkgcat)],
        assembly_type=AssemblyType.SMT
    )

    for i in range(connector.circuits):
        package.add_pad(PackagePad(pkg_uuid(connector, f'pad{i}'), Name(str(i + 1))))

    footprint = generate_footprint(connector, footprint_spec, description, reverse_pad_order)

    package.add_footprint(footprint)

    return package


# takes in the package, and binds it to a pinsocket (from LibrePCB Connectors) component with the same number of pins.
def generate_dev(
    package: Package,
    connector: Connector,
    description: str,
    keywords: str,
    author: str,
    devcat: str,
    version: str,
    create_date: Optional[str],
    generated_by: str,
    dev_name: str
) -> Device:

    component_uuid = lookup_connector_component(1, connector.circuits)
    signal_uuids = lookup_connector_component_signal(1, connector.circuits)

    dev = Device(
        uuid=dev_uuid(connector, 'dev'),
        name=Name(dev_name),
        description=Description(description),
        keywords=Keywords(keywords),
        author=Author(author),
        version=Version(version),
        created=Created(create_date or now()),
        deprecated=Deprecated(False),
        generated_by=GeneratedBy(generated_by),
        categories=[Category(devcat)],
        component_uuid=ComponentUUID(component_uuid),
        package_uuid=PackageUUID(package.uuid),
    )

    # only connect actual circuits (pins) to signals
    # the support pads are left unconnected (as per library conventions)
    for i in range(connector.circuits):
        dev.add_pad(ComponentPad(pkg_uuid(connector, f'pad{i}'), SignalUUID(signal_uuids[i])))

    return dev


def generate_jst(
    library: str,
    pkg_type: str,
    pkg_subtype: str,
    description: str,
    keywords: str,
    author: str,
    pkgcat: str,
    devcat: str,
    version: str,
    create_date: Optional[str],
    generated_by: str,
    footprint_spec: FootprintSpecification,
    available_circuits: Iterable[int],
    device_naming_pattern: str,
    reverse_pad_order: bool
) -> None:

    for circuits in available_circuits:

        conn = Connector(pkg_type, pkg_subtype, circuits)

        pkg = generate_pkg(
            connector=conn,
            description=description,
            keywords=keywords,
            author=author,
            pkgcat=pkgcat,
            version=version,
            create_date=create_date,
            generated_by=generated_by,
            footprint_spec=footprint_spec,
            reverse_pad_order=reverse_pad_order
        )

        dev = generate_dev(
            package=pkg,
            connector=conn,
            description=description,
            keywords=keywords,
            author=author,
            devcat=devcat,
            version=version,
            create_date=create_date,
            generated_by=generated_by,
            dev_name=device_naming_pattern.format(f"{circuits:02d}").upper().replace(' ', '-')
        )

        write_pkg(library, pkg)
        write_dev(library, dev)


if __name__ == "__main__":
    # units in mm
    generate_jst(
        library="JST.lplib",
        pkg_type="SH",
        pkg_subtype="SM",
        description="Header SR 1.0 SMT side entry",
        keywords="connector,jst,j",  # taken from https://jst.de/product-family/show/65/sh
        author="nbes4",
        generated_by="nbes4",
        pkgcat="2f9c28ee-8507-45be-8c06-591549d8bee3",
        devcat="e4c9b084-7ee2-4310-9b5c-dc66c736a6e0",
        version="0.1",
        footprint_spec=FootprintSpecification(
            pad_width=0.6,
            pad_height=1.55,
            lead_width=0.6,
            lead_height=0.7,
            support_pad_width=1.2,
            support_pad_height=1.8,
            # the smallest SH SM connector is 4 mm and has 2 pins,
            # for every additional pin the width increases by 1 mm
            smallest_header_width=4,
            header_width_increase_per_pin=1,
            header_height=4.25,
            header_y=0.2,
            pad_distance_mid_to_mid_x=1,
            pad_first_x_center=1.2 + 0.4 + (0.6 / 2),
            pad_first_y_center=4 + (1.55 / 2),
        ),
        available_circuits=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20],
        device_naming_pattern="SM{}B-SRSS-TB",
        create_date=None,
        reverse_pad_order=True
    )

    generate_jst(
        library="JST.lplib",
        pkg_type="SH",
        pkg_subtype="BM",
        description="Header SR 1.0 SMT top entry",
        keywords="connector,jst,j",
        author="nbes4",
        generated_by="nbes4",
        pkgcat="2f9c28ee-8507-45be-8c06-591549d8bee3",
        devcat="e4c9b084-7ee2-4310-9b5c-dc66c736a6e0",
        version="0.1",
        footprint_spec=FootprintSpecification(
            pad_width=0.6,
            pad_height=1.55,
            lead_width=0.6,
            lead_height=0.7,
            support_pad_width=1.2,
            support_pad_height=1.8,
            # the smallest SH BM connector is 4 mm and has 2 pins,
            # for every additional pin the width increases by 1 mm
            smallest_header_width=4,
            header_width_increase_per_pin=1,
            header_height=2.9,
            header_y=0.2,
            pad_distance_mid_to_mid_x=1,
            pad_first_x_center=1.2 + 0.4 + (0.6 / 2),
            pad_first_y_center=2.65 + (1.55 / 2),
        ),
        available_circuits=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        device_naming_pattern="BM{}B-SRSS-TB",
        create_date=None,
        reverse_pad_order=False
    )

    save_cache(uuid_cache_file, uuid_cache)