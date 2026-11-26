"""Split a Java test file into the method texts that get embedded.

What is embedded for one test-class file (``select_methods``), in order of preference:

1. ``test``: its test methods: annotated ``@Test`` / ``@ParameterizedTest`` / ``@RepeatedTest`` /
   ``@TestFactory`` / ``@TestTemplate``, or JUnit 3 style (public void ``test*()`` with no parameters);
2. ``all``: every method, for classes whose tests are inherited or generated;
3. ``file``: the whole file, when no method could be parsed.

Methods of all classes in the file count (inner classes included); bodies are not searched, so methods of
anonymous classes inside a test stay part of that test. Text follows the FALCON artifact: the method
source with line breaks turned into spaces; annotations are dropped (they carry no behaviour and
``@Test(timeout=...)`` would make otherwise equal tests differ). The tokenizer truncates to 512 tokens.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache

TEST_ANNOTATIONS = frozenset({"Test", "ParameterizedTest", "RepeatedTest", "TestFactory", "TestTemplate"})
ANNOTATION_NODES = ("marker_annotation", "annotation")
TYPE_NODES = ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
              "annotation_type_declaration")


@dataclass(frozen=True)
class Method:
    name: str
    owner: str      # enclosing type path, e.g. "FooTest" or "FooTest.Inner"
    text: str       # embedded text
    is_test: bool


@dataclass(frozen=True)
class ParsedFile:
    package: str | None
    methods: tuple
    has_error: bool


@lru_cache(maxsize=1)
def _parser():
    import tree_sitter_java as tsj
    from tree_sitter import Language, Parser

    return Parser(Language(tsj.language()))


def _flat(text: str) -> str:
    return text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")


def _annotation_name(node, src: bytes) -> str:
    name = node.child_by_field_name("name")
    raw = src[name.start_byte:name.end_byte].decode("utf-8", "replace") if name else ""
    return raw.rsplit(".", 1)[-1]


def _method(node, src: bytes, owner: str) -> Method:
    name_node = node.child_by_field_name("name")
    name = src[name_node.start_byte:name_node.end_byte].decode("utf-8", "replace") if name_node else ""
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    annotations, keywords = [], []
    if mods is not None:
        for c in mods.children:
            if c.type in ANNOTATION_NODES:
                annotations.append(_annotation_name(c, src))
            else:
                keywords.append(src[c.start_byte:c.end_byte].decode("utf-8", "replace"))
        rest = src[mods.end_byte:node.end_byte].decode("utf-8", "replace")
        text = " ".join(keywords + [rest.lstrip()]) if keywords else rest.lstrip()
    else:
        text = src[node.start_byte:node.end_byte].decode("utf-8", "replace")

    params = node.child_by_field_name("parameters")
    no_params = params is None or not any(c.is_named for c in params.children)
    rtype = node.child_by_field_name("type")
    is_void = rtype is not None and rtype.type == "void_type"
    junit3 = name.startswith("test") and "public" in keywords and is_void and no_params
    return Method(name=name, owner=owner, text=_flat(text),
                  is_test=bool(TEST_ANNOTATIONS.intersection(annotations)) or junit3)


def parse_java(source) -> ParsedFile:
    src = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    tree = _parser().parse(src)
    package, methods = None, []

    def visit(node, owner):
        nonlocal package
        for c in node.children:
            if c.type == "package_declaration":
                ident = next((x for x in c.children if x.type in ("scoped_identifier", "identifier")), None)
                if ident is not None:
                    package = src[ident.start_byte:ident.end_byte].decode("utf-8", "replace")
            elif c.type in TYPE_NODES:
                n = c.child_by_field_name("name")
                name = src[n.start_byte:n.end_byte].decode("utf-8", "replace") if n else "?"
                body = c.child_by_field_name("body")
                if body is not None:
                    visit(body, f"{owner}.{name}" if owner else name)
            elif c.type == "method_declaration":
                methods.append(_method(c, src, owner))
            elif c.type in ("class_body", "interface_body", "enum_body", "enum_body_declarations",
                            "annotation_type_body", "record_body"):
                visit(c, owner)

    visit(tree.root_node, "")
    return ParsedFile(package=package, methods=tuple(methods), has_error=tree.root_node.has_error)


def select_methods(parsed: ParsedFile, source) -> tuple[str, list[str]]:
    """(kind, texts) to embed for one file; kind is 'test', 'all' or 'file'."""
    tests = [m.text for m in parsed.methods if m.is_test]
    if tests:
        return "test", tests
    if parsed.methods:
        return "all", [m.text for m in parsed.methods]
    text = source.decode("utf-8", "replace") if isinstance(source, (bytes, bytearray)) else source
    return "file", [_flat(text)]


def text_id(text: str) -> str:
    """Content id of an embedded text (identical methods across files and versions are embedded once)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]
