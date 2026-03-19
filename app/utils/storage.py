"""文件存储与目录管理工具。"""

from pathlib import Path
from typing import Optional

from fastapi import UploadFile


def ensure_directory(path: Path) -> None:
    """确保目录存在。"""

    path.mkdir(parents=True, exist_ok=True)


async def save_upload_file(
    upload: UploadFile, destination: Path, overwrite: bool = True
) -> int:
    """保存上传文件到指定路径，返回字节大小。

    由于 ``UploadFile`` 在 FastAPI 中是异步文件对象，这里使用 ``await upload.read()``
    读取全部内容，然后写入目标路径。对于大文件可改为分块读取。
    """

    ensure_directory(destination.parent)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"{destination} already exists and overwrite is False")

    data = await upload.read()
    with destination.open("wb") as f:
        f.write(data)
    await upload.seek(0)
    return len(data)


def remove_directory(path: Path) -> None:
    """递归删除目录，忽略不存在的情况。"""

    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            remove_directory(child)
        else:
            child.unlink(missing_ok=True)
    path.rmdir()
