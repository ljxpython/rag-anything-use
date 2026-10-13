"""Accepted original formats and bounded validation before an upload ticket exists."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

TEXT_MIME = {"text/plain": "txt", "text/markdown": "md"}
DOCUMENT_MIME = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "image/png": "png",
    "image/jpeg": "jpg",
}
MIME_EXT = {**TEXT_MIME, **DOCUMENT_MIME}


def document_processing_available(config):
    if config.parser_name != "docling" or not all(
        (
            config.enable_image_processing,
            config.enable_table_processing,
            config.enable_equation_processing,
        )
    ):
        return False
    try:
        for package in ("raganything", "docling", "pillow", "pypdf"):
            version(package)
    except PackageNotFoundError:
        return False
    return True


def supported_mime_types(config):
    return list(MIME_EXT if document_processing_available(config) else TEXT_MIME)


def validate_original(path, mime_type, max_bytes):
    """Validate the actual container; file name and declared MIME are insufficient."""
    path = Path(path)
    try:
        if mime_type in TEXT_MIME:
            text = path.read_text(encoding="utf-8")
            if not text.strip() or "\x00" in text:
                raise ValueError
        elif mime_type == "application/pdf":
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError

            with path.open("rb") as handle:
                if not handle.read(8).startswith(b"%PDF-"):
                    raise ValueError
                handle.seek(0)
                try:
                    pdf = PdfReader(handle, strict=True)
                    if pdf.is_encrypted or not len(pdf.pages):
                        raise ValueError
                except PdfReadError:
                    raise ValueError from None
        elif MIME_EXT.get(mime_type) in {"docx", "pptx"}:
            with ZipFile(path) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 4096
                    or len({i.filename for i in entries}) != len(entries)
                    or sum(i.file_size for i in entries) > max_bytes * 5
                ):
                    raise ValueError
                for item in entries:
                    name = PurePosixPath(item.filename)
                    if (
                        name.is_absolute()
                        or ".." in name.parts
                        or "\\" in item.filename
                        or item.flag_bits & 1
                        or (item.external_attr >> 16) & 0o170000 == 0o120000
                    ):
                        raise ValueError
                required = (
                    "word/document.xml"
                    if MIME_EXT[mime_type] == "docx"
                    else "ppt/presentation.xml"
                )
                for name in ("[Content_Types].xml", required):
                    root = ElementTree.fromstring(archive.read(name))
                    if name == required and root.tag.rsplit("}", 1)[-1] != (
                        "document" if MIME_EXT[mime_type] == "docx" else "presentation"
                    ):
                        raise ValueError
                if archive.testzip() is not None:
                    raise ValueError
        elif mime_type in {"image/png", "image/jpeg"}:
            from PIL import Image

            with Image.open(path) as image:
                if image.format != ("PNG" if mime_type == "image/png" else "JPEG"):
                    raise ValueError
                if image.width * image.height > 40_000_000:
                    raise ValueError
                image.verify()
        else:
            raise ValueError("knowledge_unsupported_format")
    except (
        OSError,
        ValueError,
        UnicodeError,
        BadZipFile,
        KeyError,
        ElementTree.ParseError,
    ):
        raise ValueError("knowledge_invalid_content") from None
