import re
import gi

from .resources import Fonts, Images, Seals

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo
import cairo

SCALE_192 = 7.559
SCALE_128 = 5.039
COMMANDS = set("SMLQBAC")
COMMAND_RE = re.compile(r"([SMLQBAC])")
FLOAT_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?")

font_map = PangoCairo.font_map_get_default()
# print(
#     [
#         f.get_name()
#         for f in font_map.list_families()
#         if "song" in f.get_name().lower()
#         or "cour" in f.get_name().lower()
#         or "kai" in f.get_name().lower()
#     ]
# )


def _tokenize_path(pathdef):
    for x in COMMAND_RE.split(pathdef):
        if x in COMMANDS:
            yield x
        for token in FLOAT_RE.findall(x):
            yield token


def _draw_AbbreviatedData(
    draw, boundary, path, fillColor=(128, 128, 128), lineWidth=2, scale=SCALE_192
):
    x_start = boundary[0]
    y_start = boundary[1]
    current_pos = (x_start, y_start)

    elements = list(_tokenize_path(path))
    elements.reverse()

    while elements:
        if elements[-1] in COMMANDS:
            command = elements.pop()
        else:
            raise Exception("操作符违法")

        if command == "M":
            x = scale * float(elements.pop())
            y = scale * float(elements.pop())
            pos = (x_start + x, y_start + y)
            current_pos = pos

        elif command == "L":
            x = scale * float(elements.pop())
            y = scale * float(elements.pop())
            pos = (x_start + x, y_start + y)
            draw.line(current_pos + pos, fill=fillColor, width=lineWidth)

        elif command == "B":
            pass


def _cairo_draw_path(cr, boundary, path):
    x_start = boundary[0]
    y_start = boundary[1]
    current_pos = (x_start, y_start)
    # cr.translate(x_start, y_start)
    elements = list(_tokenize_path(path))
    elements.reverse()

    command = None
    while elements:
        if elements[-1] in COMMANDS:
            command = elements.pop()
        else:
            raise Exception("操作符违法")

        if command == "M":
            x = float(elements.pop())
            y = float(elements.pop())
            cr.move_to(x, y)

        elif command == "L":
            x = float(elements.pop())
            y = float(elements.pop())
            # pos = (x_start + x, y_start + y)
            cr.line_to(x, y)
            # draw.line(current_pos + pos, fill=fillColor, width=lineWidth)

        elif command == "B":
            x1 = float(elements.pop())
            y1 = float(elements.pop())
            x2 = float(elements.pop())
            y2 = float(elements.pop())
            x3 = float(elements.pop())
            y3 = float(elements.pop())
            cr.curve_to(x1, y1, x2, y2, x3, y3)
        elif command == "A":
            # cr.arc()
            pass
        elif command == "Q":
            x1 = float(elements.pop())
            y1 = float(elements.pop())
            x2 = float(elements.pop())
            y2 = float(elements.pop())
            cr.curve_to(x1, y1, x1, y1, x2, y2)
        elif command == "C":
            pass


def _trans_Delta(elements, scale=SCALE_192):
    parsed = []
    elements.reverse()
    while elements:
        e = elements.pop()
        if e == "g":
            c = int(elements.pop())
            v = float(elements.pop())
            parsed += c * [v * scale]
        else:
            parsed.append(float(e) * scale)
    # print('_trans_Delta', elements, parsed)
    return parsed


def cairo_path(cr, node):
    lineWidth = float(node.attr["LineWidth"]) if "LineWidth" in node.attr else 0.5
    boundary = [float(i) for i in node.attr["Boundary"].split(" ")]
    ctm = None
    if "CTM" in node.attr:
        ctm = [float(i) for i in node.attr["CTM"].split(" ")]
    fillColor = [0, 0, 0]
    if "FillColor" in node:
        fillColor = [
            float(i) / 255.0 for i in node["FillColor"].attr["Value"].split(" ")
        ]
    strokeColor = [0, 0, 0]
    if "StrokeColor" in node:
        strokeColor = [
            float(i) / 255.0 for i in node["StrokeColor"].attr["Value"].split(" ")
        ]
    # print('draw path', boundary, fillColor, strokeColor)
    AbbreviatedData = node["AbbreviatedData"].text
    cr.save()
    if ctm:
        # 如果有ctm，对cr进行的矩阵变换
        # print('cairo path ctm:', ctm)
        ctm_matrix = cairo.Matrix(*ctm)
        _, mx, my, _, lx, ly = AbbreviatedData.strip().split(" ")
        mx, my = ctm_matrix.transform_point(float(mx), float(my))
        lx, ly = ctm_matrix.transform_point(float(lx), float(ly))
        AbbreviatedData = f"M {mx} {my} L {lx} {ly}"
        lineWidth = ctm_matrix.transform_distance(lineWidth, 0)[0]
    cr.translate(boundary[0], boundary[1])

    cr.set_source_rgba(*strokeColor)
    cr.set_line_width(lineWidth)
    _cairo_draw_path(cr, boundary, AbbreviatedData)
    cr.stroke()
    cr.restore()


def cairo_text(cr, node):
    boundary = [float(i) for i in node.attr["Boundary"].split(" ")]
    ctm = None
    if "CTM" in node.attr:
        ctm = [float(i) for i in node.attr["CTM"].split(" ")]
    font_id = node.attr["Font"]
    font_family = get_font_from_id(font_id).get_font_family()
    font_size = float(node.attr["Size"]) / 1.3
    fillColor = [0, 0, 0]
    if "FillColor" in node:
        fillColor = [
            float(i) / 255.0 for i in node["FillColor"].attr["Value"].split(" ")
        ]

    strokeColor = [0, 0, 0]
    if "StrokeColor" in node:
        strokeColor = [
            float(i) / 255.0 for i in node["StrokeColor"].attr["Value"].split(" ")
        ]

    TextCode = node["TextCode"]
    text = TextCode.text
    # print(f'cario text {text}, {font_id}')

    deltaX = None
    deltaY = None
    if "DeltaX" in TextCode.attr:
        deltaX = _trans_Delta(TextCode.attr["DeltaX"].split(" "), scale=1)
    if deltaX and len(deltaX) + 1 != len(text):
        # raise Exception('TextCode DeltaX 与字符个数不符')
        deltaX = deltaX[: len(text) - 1]

    if "DeltaY" in TextCode.attr:
        deltaY = _trans_Delta(TextCode.attr["DeltaY"].split(" "), scale=1)
    if deltaY and len(deltaY) + 1 != len(text):
        # raise Exception('TextCode DeltaY 与字符个数不符')
        deltaY = deltaY[: len(text) - 1]

    X = float(TextCode.attr["X"])
    Y = float(TextCode.attr["Y"])
    for idx, rune in enumerate(text):
        cr.save()
        # cr.identity_matrix()
        # cr.scale(SCALE_128, SCALE_128)
        layout = PangoCairo.create_layout(cr)
        layout.set_text(rune, -1)
        # print(font_family, rune)
        desc = Pango.FontDescription.from_string(f"{font_family} {font_size}")
        layout.set_font_description(desc)

        ink_rect, logical_rect = layout.get_pixel_extents()
        r_w, r_h = layout.get_size()
        baseline = layout.get_baseline() / Pango.SCALE
        # print(f'{rune}, baseline: {baseline}, X:{X}, Y:{Y} Boundary:{boundary}')

        offset_x = sum(deltaX[:idx]) if deltaX else 0
        offset_y = sum(deltaY[:idx]) if deltaY else 0
        # cr.move_to(boundary[0] + offset_x, boundary[1] + offset_y)
        cr.move_to(boundary[0], boundary[1])
        if ctm:
            matrix = cr.get_matrix().multiply(cairo.Matrix(*ctm))
            cr.set_matrix(matrix)
        cr.rel_move_to(X + offset_x, Y + offset_y)

        cr.set_source_rgb(*fillColor)
        # PangoCairo.show_layout(cr, layout)
        PangoCairo.show_layout_line(cr, layout.get_line(0))
        cr.restore()
    pass


def cairo_image(cr, node):
    resource_id = node.attr["ResourceID"]
    boundary = [float(i) for i in node.attr["Boundary"].split(" ")]
    ctm = None
    if "CTM" in node.attr:
        ctm = [float(i) for i in node.attr["CTM"].split(" ")]
    img_surface = get_res_image(resource_id).get_cairo_surface()

    cr.save()
    x, y = boundary[0], boundary[1]
    width, height = cr.get_matrix().transform_point(boundary[2], boundary[3])
    x, y = cr.get_matrix().transform_point(x, y)

    # 画图片是fillparent，自己重新计算缩放matrix， 同时缩放基础点x，y
    matrix = cairo.Matrix(
        width / img_surface.get_width(), 0, 0, height / img_surface.get_height(), 0, 0
    )
    if ctm:  # 再过几天，我保证不记得自己为什么会这么写
        matrix = cairo.Matrix(*map(lambda x: x * SCALE_192, ctm))
        matrix.scale(img_surface.get_width() ** -1, img_surface.get_height() ** -1)
    cr.identity_matrix()
    cr.set_matrix(matrix)
    matrix.invert()
    cr.set_source_surface(img_surface, x, y)
    cr.paint()
    cr.restore()
    pass


def cairo_seal(cr, node):
    seal_id = node.attr["ID"]
    boundary = [float(i) for i in node.attr["Boundary"].split(" ")]
    width, height = boundary[2], boundary[3]
    seal_surface = get_res_seal(seal_id).get_cairo_surface()

    cr.save()
    x, y = boundary[0], boundary[1]
    width, height = boundary[2], boundary[3]
    cr.translate(x, y)
    cr.scale(
        width / seal_surface.get_width(), height / seal_surface.get_height()
    )
    cr.set_source_surface(seal_surface)
    cr.paint()
    cr.restore()


def get_font_from_id(font_id):
    return Fonts.get(font_id)


def get_res_image(res_id):
    return Images.get(res_id)


def get_res_seal(seal_id):
    return Seals.get(seal_id)
