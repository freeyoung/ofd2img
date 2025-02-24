import os
import platform
import gi
from PIL import Image as PILImage
from io import BytesIO

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo
import cairo
import asn1
from subprocess import Popen, PIPE


Fonts = {}
MultiMedias = {}
Images = {}
Seals = {}
font_map = PangoCairo.font_map_get_default()
Cairo_Font_Family_Names = [f.get_name() for f in font_map.list_families()]
# print(Cairo_Font_Family_Names)
# print(
#     [
#         f.get_name()
#         for f in font_map.list_families()
#         if "sun" in f.get_name().lower()
#         or "cour" in f.get_name().lower()
#         or "kai" in f.get_name().lower()
#     ]
# )

OFD_FONT_MAP = {
    # 纯西文
    "Calibri": ["Calibri"],
    "Courier New": ["Courier New", "Courier"],
    "TimesNewRomanPSMT": ["Times New Roman"],
    "TimesNewRomanPS-BoldMT": ["Times New Roman"],

    # 方正 E 系列
    # Ref: http://www.cnprint.org/bbs/archive/index.php/t-193367.html
    "E-BX": ["FZShuSong-Z01"],
    "E-BZ": ["FZShuSong-Z01"],
    "E-B6": ["FZShuSong-Z01"],
    "E-F1": ["FZHei-B01"],
    "E-FZ": ["FZHei-B01"],

    # 楷体系列
    "楷体": ["KaiTi", "Kai"],
    "KaiTi": ["KaiTi", "Kai"],
    "方正楷体_GBK": ["FZKai-Z03"],
    "FZKTK--GBK1-0": ["FZKai-Z03"],

    # 宋体系列
    "宋体": ["SimSun", "STSong"],
    "SimSun": ["SimSun", "STSong"],
    "*SimSun-4399": ["SimSun", "STSong"],
    "*Adobe Song Std L-Bold-4400": ["SimSun", "STSong"],

    # 仿宋系列
    "仿宋": ["FangSong_GB2312"],
    "FangSong_GB2312": ["FangSong_GB2312"],
    "方正仿宋_GBK": ["FZFangSong-Z02"],
    "FangSong": ["FZFangSong-Z02"],
    "FZFSK--GBK1-0": ["FZFangSong-Z02"],
    "*FangSong-4401": ["FZFangSong-Z02"],
    "*FangSong-4403": ["FZFangSong-Z02"],
    "*FangSong-Bold-4402": ["FZFangSong-Z02"],

    # 黑体系列
    "SimHei": ["FZHei-B01"],
    "方正黑体_GBK": ["FZHei-B01"],
    "FZHTK--GBK1-0": ["FZHei-B01"],

    "FZXBSK--GBK1-0": ["FZXiaoBiaoSong-B05"],
    "FZXBSJW--GB1-0": ["FZXiaoBiaoSong-B05"],
    "方正小标宋_GBK": ["FZXiaoBiaoSong-B05"],
    "方正小标宋简体": ["FZXiaoBiaoSong-B05"],
    "FZS3K--GBK1-0": ["FZSong III-Z05"],
    "方正宋三_GBK": ["FZSong III-Z05"],

    "FZSSK--GBK1-0": ["FZShuSong-Z01"],
    "方正书宋_GBK": ["FZShuSong-Z01"],

}


class ResNotFoundException(Exception):
    """
    资源文件找不到
    """

    pass


class Font(object):
    ID = ""
    FontName = ""
    FamilyName = ""

    def __init__(self, attr):
        self.ID = attr["ID"] if "ID" in attr else ""
        self.FontName = attr["FontName"] if "FontName" in attr else ""
        self.FamilyName = attr["FamilyName"] if "FamilyName" in attr else ""

    def get_font_family(self):
        # fixme: 印章的Font只有FontName， 沒有FamilyName
        if self.FontName in OFD_FONT_MAP:
            candidates = OFD_FONT_MAP[self.FontName]
            for c in candidates:
                if c in Cairo_Font_Family_Names:
                    return c
        if bool(os.getenv('OFD_FONT_MUST_EXIST')):
            raise ResNotFoundException(f"Can't find font '{self.FontName}' and its replacements {OFD_FONT_MAP[self.FontName]}!")
        return self.FontName

    def __repr__(self):
        return f"ID:{self.ID}, FontName:{self.FontName} FamilyName:{self.FamilyName}, System:{self.get_font_family()}"


class MultiMedia(object):
    def __init__(self, node):
        self.ID = node.attr["ID"]
        self.Type = node.attr["Type"]
        self.location = node["MediaFile"].text

    @staticmethod
    def parse_from_node(node):
        pass


class Image(MultiMedia):
    def __init__(self, node, _zf, work_folder: str):
        super().__init__(node)
        self.png_location = None
        self.Format = node.attr["Format"] if "Format" in node.attr else "png"
        suffix = self.location.split(".")[-1]
        if suffix == "jb2":
            jb2_path = [loc for loc in _zf.namelist() if self.location in loc][0]

            x_path = _zf.extract(jb2_path, path=work_folder)
            png_path = x_path.replace(".jb2", ".png")
            pbm_path = x_path.replace(".jb2", ".pbm")

            if platform.system() == "Windows":
                Popen(["./bin/jbig2dec", "-o", png_path, x_path], stdout=PIPE).communicate()
            else:
                Popen(["jbig2dec", "-o", pbm_path, x_path], stdout=PIPE).communicate()
                with PILImage.open(pbm_path) as im:
                    im.save(png_path)

            self.png_location = png_path
        elif suffix in ("jpg", "jpeg", "bmp") or self.Format.lower() in ("jpg", "bmp"):
            img_src_path = [loc for loc in _zf.namelist() if self.location in loc][0]

            x_path = _zf.extract(img_src_path, path=work_folder)
            png_path = x_path.replace(f".{suffix}", ".png")

            with PILImage.open(x_path) as im:
                im.save(png_path)
            self.png_location = png_path

    def get_cairo_surface(self):
        if self.png_location:
            return cairo.ImageSurface.create_from_png(self.png_location)
        return None

    def __repr__(self):
        return f"Image ID:{self.ID}, Format:{self.Format}"


class Seal(Image):
    def __init__(self, node, _zf, work_folder: str):
        self.ID = node.attr["ID"]
        self.Type = node.attr["Type"]
        self.location = node.attr["BaseLoc"].split("/")[0]
        self.png_location = None
        self.Format = "png"

        signedvalue_loc = [
            loc for loc in _zf.namelist()
            if f'{self.location}/SignedValue.dat' in loc
        ][0]
        signedvalue_path = _zf.extract(signedvalue_loc, path=work_folder)

        # ASN1 在线调试工具 https://lapo.it/asn1js/
        # 从 SignedValue.dat 中解析出签章的数据
        with open(signedvalue_path, "rb") as f:
            signedvalue_data = f.read()
        decoder = asn1.Decoder()
        decoder.start(signedvalue_data)
        decoder.enter()
        decoder.enter()
        _, value = decoder.read()
        decoder.enter()
        decoder.enter()
        _, value = decoder.read()
        _, value = decoder.read()
        _, value = decoder.read()
        decoder.enter()
        _, value = decoder.read()  # value = 'gif'
        _, value = decoder.read()  # value = b'GIF89a....'

        png_path = signedvalue_path.replace("SignedValue.dat", f"seal_{self.ID}.png")
        with PILImage.open(BytesIO(value)) as im:
            im.save(png_path)
        self.png_location = png_path

    def __repr__(self):
        return f"Seal ID:{self.ID} Format:{self.Format}"


def res_add_font(node, _zf, work_folder):
    Fonts[node.attr["ID"]] = Font(node.attr)


def res_add_multimedia(node, _zf, work_folder):
    if node.attr["Type"] == "Image":
        image = Image(node, _zf, work_folder)
        Images[node.attr["ID"]] = image


def res_add_signature(node, _zf, work_folder):
    if node.attr["Type"] == "Seal":
        seal = Seal(node, _zf, work_folder)
        Seals[node.attr["ID"]] = seal
