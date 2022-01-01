# ofd2img
## Prerequisite

1. Install [PyGobject](https://pygobject.readthedocs.io/en/latest/).

    Windows 用户请参阅 [官方指引](https://pygobject.readthedocs.io/en/latest/getting_started.html#windows-getting-started)；

    Linux / macOS 用户请直接使用 pip 安装：

    ```bash
    $ pip install pygobject
    ```

2. Install [Jbig2Dec](https://github.com/ArtifexSoftware/jbig2dec)

    Windows 的 exe 版本已包含在仓库内；

    Linux / macOS 可以使用相应的包管理器安装:

    ```bash
    # Debian/Ubuntu
    $ apt install jbig2dec
    ```

    ```bash
    # macOS
    $ brew install jbig2dec
    ```
## Usage

安装好对应的依赖，调用 `OFDFile.draw_document()` 会生成 PNG 图片。

```python
from core.document import OFDFile
doc = OFDFile('test.ofd')
doc.draw_document()
# check test_Doc_0_Page_0.png under folder
```

若要测试效果可以将 OFD 文件放在仓库根目录的 ofds 文件夹下，然后执行 `ofd_test.py`。

## FAQ

1. 纯文字版 OFD 转换时报错 `KeyError: 'could not find foreign type Context'`?

    如果是 Debian/Ubuntu: `apt install python3-gi-cairo`

# Need Help?
有任何问题请提 Issue。
