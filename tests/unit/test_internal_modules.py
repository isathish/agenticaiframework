"""Unit tests for stdlib-only ``_internal/*`` modules.

These tests exercise the framework's zero-dependency replacements without
making any network calls. Network-bound tests should live elsewhere.
"""

from __future__ import annotations

import io
import json
import os
import socket
import threading
import unittest
from contextlib import closing


from agenticaiframework._internal import array as aarr
from agenticaiframework._internal import html as ahtml
from agenticaiframework._internal import http as ahttp
from agenticaiframework._internal import pdf as apdf
from agenticaiframework._internal import schema as aschema
from agenticaiframework._internal import tokenizer as atok
from agenticaiframework._internal import vector_store as avs
from agenticaiframework._internal import yaml as ayaml
from agenticaiframework._internal import jwt as ajwt
from agenticaiframework._internal import http_server as asrv
from agenticaiframework._internal import ws as aws


class TestArray(unittest.TestCase):
    def test_dot_norm_cosine(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(aarr.dot(a, a), 1.0)
        self.assertAlmostEqual(aarr.norm(a), 1.0)
        self.assertAlmostEqual(aarr.cosine(a, b), 0.0)
        self.assertAlmostEqual(aarr.cosine(a, a), 1.0)

    def test_topk(self):
        out = aarr.topk([0.1, 0.9, 0.5, 0.2], 2)
        # topk returns [(index, value), ...] sorted by value desc.
        idxs = [i for i, _ in out]
        self.assertEqual(idxs[0], 1)
        self.assertIn(2, idxs)


class TestHTML(unittest.TestCase):
    def test_parse_and_select(self):
        doc = ahtml.parse_html(
            "<html><body><div class='post'><h1>Hi</h1><p>Hello</p></div></body></html>"
        )
        h1 = doc.find("h1")
        self.assertIsNotNone(h1)
        self.assertEqual(h1.text.strip(), "Hi")
        posts = doc.find_all("div")
        self.assertEqual(len(posts), 1)


class TestYAML(unittest.TestCase):
    def test_round_trip(self):
        text = """
name: agent
tags:
  - a
  - b
config:
  retries: 3
  active: true
""".lstrip()
        data = ayaml.safe_load(text)
        self.assertEqual(data["name"], "agent")
        self.assertEqual(data["tags"], ["a", "b"])
        self.assertEqual(data["config"]["retries"], 3)
        self.assertIs(data["config"]["active"], True)
        # Dump → reload should be stable.
        again = ayaml.safe_load(ayaml.dump(data))
        self.assertEqual(again["name"], "agent")


class TestSchema(unittest.TestCase):
    def test_basemodel_validate(self):
        class Item(aschema.BaseModel):
            name: str
            qty: int = 1

        obj = Item.model_validate({"name": "apple", "qty": 3})
        self.assertEqual(obj.name, "apple")
        self.assertEqual(obj.qty, 3)
        with self.assertRaises(aschema.ValidationError):
            Item.model_validate({"qty": "x"})

    def test_validate_against_schema(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        self.assertEqual(aschema.validate({"name": "x"}, schema), [])
        self.assertNotEqual(aschema.validate({}, schema), [])


class TestTokenizer(unittest.TestCase):
    def test_count_tokens(self):
        n = atok.count_tokens("hello world", "gpt-4o")
        self.assertGreater(n, 0)

    def test_count_messages(self):
        msgs = [{"role": "user", "content": "hello"}]
        self.assertGreater(atok.count_message_tokens(msgs, "gpt-4o"), 0)


class TestVectorStore(unittest.TestCase):
    def test_memory_store(self):
        store = avs.create_store("memory")
        store.upsert(avs.VectorEntry(id="a", vector=[1.0, 0.0], metadata={"k": 1}))
        store.upsert(avs.VectorEntry(id="b", vector=[0.0, 1.0], metadata={"k": 2}))
        results = store.search([1.0, 0.0], top_k=1)
        self.assertEqual(results[0][0].id, "a")

    def test_sqlite_store(self, tmpdir=None):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            store = avs.create_store("sqlite", path=os.path.join(d, "v.db"))
            store.upsert(avs.VectorEntry(id="x", vector=[1.0]))
            self.assertEqual(store.count(), 1)


class TestPDF(unittest.TestCase):
    def test_writer_then_reader(self):
        writer = apdf.PdfWriter()
        writer.add_page("Hello world")
        writer.add_page("Page two text")
        data = writer.to_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        reader = apdf.PdfReader(data=data)
        # Best-effort extraction — we just verify it parses without error.
        self.assertGreaterEqual(reader.num_pages, 1)


class TestJWT(unittest.TestCase):
    def test_hs256_round_trip(self):
        token = ajwt.encode({"sub": "alice"}, "secret", algorithm="HS256")
        payload = ajwt.decode(token, "secret", algorithms=["HS256"])
        self.assertEqual(payload["sub"], "alice")

    def test_hs256_bad_signature(self):
        token = ajwt.encode({"sub": "alice"}, "secret")
        with self.assertRaises(ajwt.JWTError):
            ajwt.decode(token, "wrong", algorithms=["HS256"])


class TestHTTPServer(unittest.TestCase):
    def test_routing_and_dispatch(self):
        app = asrv.App()

        @app.get("/hello/{name}")
        def hello(req: asrv.Request) -> asrv.Response:
            return asrv.Response.json({"hi": req.path_params["name"]})

        req = asrv.Request(method="GET", path="/hello/world", query={}, headers={}, body=b"")
        resp = app.dispatch(req)
        self.assertEqual(resp.status, 200)
        self.assertEqual(json.loads(resp.body)["hi"], "world")

    def test_404(self):
        app = asrv.App()
        req = asrv.Request(method="GET", path="/nope", query={}, headers={}, body=b"")
        resp = app.dispatch(req)
        self.assertEqual(resp.status, 404)


class TestWSCodec(unittest.TestCase):
    def test_frame_round_trip(self):
        sock_a, sock_b = socket.socketpair()
        try:
            payload = b"Hello, websocket!"
            sock_a.sendall(aws.encode_frame(aws.OP_TEXT, payload, mask=True))
            frame = aws.read_frame(sock_b)
            self.assertEqual(frame.opcode, aws.OP_TEXT)
            self.assertEqual(frame.payload, payload)
        finally:
            sock_a.close()
            sock_b.close()


class TestMCP(unittest.TestCase):
    def test_initialize(self):
        from agenticaiframework.tools import mcp_runtime as mcp

        server = mcp.MCPServer()
        resp = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(resp["result"]["protocolVersion"], mcp.PROTOCOL_VERSION)

    def test_tools_list_empty(self):
        from agenticaiframework.tools import mcp_runtime as mcp

        # Empty registry — but the real registry might have global tools; just
        # verify the call shape returns a tools array.
        server = mcp.MCPServer()
        resp = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertIn("tools", resp["result"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
