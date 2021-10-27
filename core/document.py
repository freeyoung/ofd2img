import os
import traceback
from typing import Optional
from zipfile import ZipFile

import cssselect2
from defusedxml import ElementTree

from .constants import UNITS
from .resources import res_add_font, res_add_multimedia, res_add_signature
from .surface import cairo, cairo_path, cairo_text, cairo_image, cairo_seal
from pathlib import Path
from PIL import Image, ImageStat
from io import BytesIO
import tempfile
import shutil


class OFDFile(object):
    """
    OFD Ref:GBT_33190-2016_电子文件存储与交换格式版式文档.pdf
    """

    #: contains OFD file header data
    header = None
    #: references to document's resources
    resources = None
    zf: ZipFile

    def __init__(self, file_path):
        self.zf = ZipFile(file_path)
        # for info in self._zf.infolist():
        #     print(info)
        self.node_tree = self.read_node("OFD.xml")

        # parse node
        self.document_node = self.read_node(self.node_tree["DocBody"]["DocRoot"].text)
        self.document = OFDDocument(self.zf, self.document_node)
        # print_node_recursive(self.document_node)

    def read_node(self, location):
        document = self.zf.read(location)
        tree = ElementTree.fromstring(document)
        root = cssselect2.ElementWrapper.from_xml_root(tree)
        return Node(root)

    def draw_document(self, doc_num=0, destination: Optional[str] = None, output_format: Optional[str] = "png"):
        document = self.document
        destination = destination or "."
        destination = Path(destination)
        destination.mkdir(exist_ok=True, parents=True)
        paths = []
        for i, page in enumerate(document.pages):
            surface = Surface(page, os.path.split(self.zf.filename)[-1].strip(".ofd"))
            paths.append(
                surface.draw(page, destination / Path(f"{surface.filename}_{i}.{output_format}"))
            )
        shutil.rmtree(self.document.work_folder, ignore_errors=True)
        return paths


class OFDDocument(object):
    def __init__(self, _zf, node, n=0):
        self.pages = []
        self.signatures = []
        self._zf = _zf
        self.work_folder = tempfile.mkdtemp()
        self.name = f"Doc_{n}"
        self.node = node
        self.physical_box = [
            float(i)
            for i in node["CommonData"]["PageArea"]["PhysicalBox"].text.split(" ")
        ]
        if isinstance(node["Pages"]["Page"], list):
            sorted_pages = sorted(
                node["Pages"]["Page"], key=lambda x: int(x.attr["ID"])
            )
        else:
            sorted_pages = [node["Pages"]["Page"]]
        sorted_tpls = []
        if "TemplatePage" in node["CommonData"]:
            if isinstance(node["CommonData"]["TemplatePage"], list):
                sorted_tpls = sorted(
                    node["CommonData"]["TemplatePage"], key=lambda x: int(x.attr["ID"])
                )
            else:
                sorted_tpls = [node["CommonData"]["TemplatePage"]]
        if f"{self.name}/Signs/Signatures.xml" in self._zf.namelist():
            node = Node.from_zp_location(
                self._zf, f"{self.name}/Signs/Signatures.xml"
            )
            if isinstance(node["Signature"], list):
                for sign in node["Signature"]:
                    self.signatures.append(sign)
            else:
                self.signatures.append(node["Signature"])

        self._parse_res()
        # print('Resources:', Fonts, Images)
        # assert len(node['CommonData']['TemplatePage']) == len(node['Pages']['Page'])

        seal_nodes = {}
        for sign in (s for s in self.signatures if s.attr["Type"] == "Seal"):
            node = Node.from_zp_location(
                self._zf, f"{self.name}/Signs/{sign.attr['BaseLoc']}"
            )
            seal_node = node["SignedInfo"]["StampAnnot"]
            seal_node.attr.update({
                "ID": sign.attr["ID"],
                "BaseLoc": f"{self.name}/Signs/{sign.attr['BaseLoc']}",
            })
            seal_nodes[seal_node.attr["PageRef"]] = seal_node

        for i, p in enumerate(sorted_pages):
            page_node = Node.from_zp_location(
                _zf, self.name + "/" + sorted_pages[i].attr["BaseLoc"]
            )

            tpl_node = None
            if i < len(sorted_tpls):
                tpl_node = Node.from_zp_location(
                    _zf, self.name + "/" + sorted_tpls[i].attr["BaseLoc"]
                )

            self.pages.append(
                OFDPage(
                    self,
                    f"Page_{i}",
                    page_node,
                    tpl_node,
                    seal_nodes.get(p.attr["ID"]),
                )
            )

    def _parse_res(self):
        if "DocumentRes" in self.node["CommonData"]:
            node = Node.from_zp_location(
                self._zf, f"{self.name}/{self.node['CommonData']['DocumentRes'].text}"
            )
            self._parse_res_node(node)

        if "PublicRes" in self.node["CommonData"]:
            node = Node.from_zp_location(
                self._zf, f"{self.name}/{self.node['CommonData']['PublicRes'].text}"
            )
            self._parse_res_node(node)

        if f"{self.name}/Signs/Signatures.xml" in self._zf.namelist():
            for node in self.signatures:
                self._parse_res_node(node)

    def _parse_res_node(self, node):
        if node.tag in RESOURCE_TAGS:
            try:
                RESOURCE_TAGS[node.tag](node, self._zf, self.work_folder)
            except Exception as e:
                # Error in point parsing, do nothing
                print_node_recursive(node)
                print(traceback.format_exc())
                pass
            return  # no need to go deeper

        for child in node.children:
            self._parse_res_node(child)


class OFDPage(object):
    def __init__(self, parent: OFDDocument, name, page_node, tpl_node, seal_node):
        self.parent = parent
        self.name = f"{parent.name}_{name}"
        self.physical_box = self.parent.physical_box
        if "Area" in page_node and "PhysicalBox" in page_node["Area"]:
            self.physical_box = [
                float(i) for i in page_node["Area"]["PhysicalBox"].text.split(" ")
            ]
        self.tpl_node = tpl_node
        self.page_node = page_node
        self.seal_node = seal_node


class Surface(object):
    def __init__(self, page, name, dpi=192):
        self.page = page
        self.dpi = dpi
        self.filename = name

    @property
    def pixels_per_mm(self):
        return self.dpi * UNITS["mm"]

    def cairo_draw(self, cr, node):
        # Only draw known tags
        if node.tag in CAIRO_TAGS:
            try:
                CAIRO_TAGS[node.tag](cr, node)
            except Exception as e:
                # Error in point parsing, do nothing
                print_node_recursive(node)
                print(traceback.format_exc())
                pass
            return  # no need to go deeper

        for child in node.children:
            # Only draw known tags
            self.cairo_draw(cr, child)

    # 已经有 self.page 了，为什么这里还要传 page?
    def draw(self, page, path: Optional[str] = None) -> str:
        # 计算A4 210mm 192dpi 下得到的宽高
        physical_width = self.page.physical_box[2]
        physical_height = self.page.physical_box[3]
        width = int(physical_width * self.pixels_per_mm)
        height = int(physical_height * self.pixels_per_mm)
        # print(f"create cairo surface, width: {width}, height: {height}")
        cairo_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)

        self.cr = cairo.Context(cairo_surface)
        # scale mm to pixels
        self.cr.scale(self.pixels_per_mm, self.pixels_per_mm)
        self.cr.set_source_rgb(1, 1, 1)
        self.cr.paint()
        self.cr.move_to(0, 0)

        if self.page.tpl_node:
            self.cairo_draw(self.cr, self.page.tpl_node)
        self.cairo_draw(self.cr, self.page.page_node)

        # self.cr.scale(self.pixels_per_mm, self.pixels_per_mm)
        # draw StampAnnot
        if self.page.seal_node:
            self.cairo_draw(self.cr, self.page.seal_node)

        bio = BytesIO()
        cairo_surface.write_to_png(bio)
        cairo_surface.finish()
        path = path or f"{self.filename}_{page.name}.png"
        im = Image.open(bio)
        stat_var = ImageStat.Stat(im).var
        # detect grayscale - 100 is a naïve threshold
        if len(stat_var) == 3 and abs(max(stat_var) - min(stat_var)) < 100:
            im = im.convert("L")
        im.save(path)
        return path


CAIRO_TAGS = {
    "PathObject": cairo_path,
    "TextObject": cairo_text,
    "ImageObject": cairo_image,
    "StampAnnot": cairo_seal,
}

RESOURCE_TAGS = {
    "Font": res_add_font,
    "MultiMedia": res_add_multimedia,
    "Signature": res_add_signature,
}


class Node(dict):
    def __init__(self, element):
        super().__init__()
        self.element = element
        node = element.etree_element

        self.children = []
        self.text = node.text
        self.tag = (
            element.local_name
            if element.namespace_url in ("", "http://www.ofdspec.org/2016")
            else "{%s}%s" % (element.namespace_url, element.local_name)
        )
        self.attr = node.attrib
        for child in element.iter_children():
            child_node = Node(child)
            self.children.append(child_node)
            if child_node.tag:
                if child_node.tag in self:
                    if isinstance(self[child_node.tag], list):
                        self[child_node.tag].append(child_node)
                    else:
                        self[child_node.tag] = [self[child_node.tag], child_node]
                else:
                    self[child_node.tag] = child_node

    def __bool__(self):
        # 否则当没有 child_node.tag 的时候，作为一个 dict，会被认为是 False
        return bool(super().__len__()) or bool(self.tag)

    @staticmethod
    def from_zp_location(zf, location):
        # print('from_zp_location', location)
        document = zf.read(location)
        tree = ElementTree.fromstring(document)
        root = cssselect2.ElementWrapper.from_xml_root(tree)
        return Node(root)

    def __repr__(self):
        return f"Tag: {self.tag}, Attr: {self.attr}, Text: {self.text}"


def print_node_recursive(node, depth=0):
    print("  " * depth, node)
    for child in node.children:
        print_node_recursive(child, depth=depth + 1)
